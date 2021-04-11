import logging
import sys
import time

from fints.client import FinTS3PinTanClient
import fints_url
from getpass import getpass
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, or_
from banking import model
from datetime import date, timedelta, datetime
import argparse
import numpy as np
import math
from matplotlib import pyplot
from typing import List


logging.basicConfig(level=logging.INFO)

db_engine = sqlalchemy.create_engine('sqlite+pysqlite:///db/testing.db', echo=True, future=True)
Session = sessionmaker(db_engine)


def find_account_name(iban, info):
    name = info['bank']['name'] + ' - '
    for acc in info['accounts']:
        if acc['iban'] == iban:
            name += f"{' '.join(acc['owner_name'])} ({acc['product_name']})"
            return name

    return name + "Account"


def import_transactions(blz: str, login: str, password: str):

    fints_host = fints_url.find(bank_code=blz)
    f = FinTS3PinTanClient(blz, login, password, fints_host, product_id=None)

    with f:
        if f.init_tan_response:
            print("A TAN is required", f.init_tan_response.challenge)
            tan = input("Please enter TAN: ")
            f.send_tan(f.init_tan_response, tan)

        accounts = f.get_sepa_accounts()

        info = f.get_information()
        print(info)

        for account in accounts:
            iban = account.iban
            with Session() as session:
                if not session.query(session.query(model.Account).filter(model.Account.iban == iban).exists()).scalar():
                    balance = float(f.get_balance(account).amount.amount)
                    account_name = find_account_name(iban, info)
                    #print(f'balance: {float(balance.amount.amount)}')
                    blz = account.blz
                    bic = account.bic
                    acc_number = account.accountnumber
                    new_acc = model.Account(iban=iban, balance=balance, blz=blz, bic=bic, number=acc_number,
                                            name=account_name, type=model.Account.AccountType.ASSET)
                    session.add(new_acc)
                    print(f"Creating account: {new_acc}")
                    session.commit()

        for account in accounts:

            with Session() as session:
                own_account = session.execute(select(model.Account).filter(model.Account.iban == account.iban)).scalar()
                if own_account is None:
                    raise Exception(f"ERROR: Could not find own account with IBAN {own_iban}!")
                start_date = date.today() - timedelta(days=30)
                history_end = own_account.history_end
                if history_end is not None:
                    start_date = max(start_date, history_end.date())
                transactions = f.get_transactions(account, start_date=start_date, end_date=date.today())
                for transaction in transactions:
                    own_iban = account.iban
                    other_iban = transaction.data['applicant_iban']
                    amount = transaction.data['amount'].amount
                    transaction_date = date(int(transaction.data['date'].year), int(transaction.data['date'].month),
                                            int(transaction.data['date'].day))
                    message = transaction.data['purpose']

                    if not session.query(session.query(model.Account).filter(model.Account.iban == other_iban)
                                         .exists()).scalar():
                        balance = blz = bic = acc_number = None
                        account_name = transaction.data['applicant_name']
                        new_acc = model.Account(iban=other_iban, blz=blz, bic=bic, number=acc_number,
                                                name=account_name, balance=balance,
                                                type=model.Account.AccountType.FOREIGN)
                        session.add(new_acc)
                        session.commit()
                    other_account = session.execute(select(model.Account).filter(model.Account.iban == other_iban))\
                        .scalar()
                    source_acc = own_account if amount < 0 else other_account
                    target_acc = own_account if amount >= 0 else other_account
                    new_transaction = model.Transaction(source=source_acc, target=target_acc,
                                                        amount=abs(amount), message=message,
                                                        time=datetime.combine(transaction_date, datetime.min.time()))
                    session.add(new_transaction)
                    session.commit()


def import_cmd(args):

    pw = getpass('Please enter your Bank password: ')
    model.set_up(db_engine)
    import_transactions(args.blz, args.login, pw)


def get_account_plot(iban: str, xs: range):
    with Session() as session:
        acc: model.Account = session.execute(select(model.Account).filter(model.Account.iban == iban)).scalar()

        def y_fn(days: int, last_val: float):
            today_start = datetime.combine(date.today(), datetime.min.time())
            range_start = today_start - timedelta(days=days)
            range_end = today_start - timedelta(days=days - 1)
            print(f"Selecting transactions between {range_start} and {range_end}...")
            transactions = session.query(model.Transaction).filter(and_(
                        or_(model.Transaction.source_id == acc.id, model.Transaction.target_id == acc.id),
                        and_(range_end > model.Transaction.time, range_start <= model.Transaction.time)))
            if len(transactions.all()) == 0:
                print(f"No transactions found for day {-days}")
            result = last_val
            for t in transactions:
                result -= t.amount if t.target_id == acc.id else -t.amount
            return result

        ys = [acc.balance]
        for x in xs[1:]:
            ys.append(y_fn(x, ys[-1]))
        # print(ys)

        return ys
        # pyplot.plot(list(map(lambda a: -a, reversed(xs))), list(reversed(ys)))


def plot_cmd(args):
    xs = range(0, args.days)
    if args.iban == 'all':
        with Session() as session:
            accounts = session.query(model.Account).filter(model.Account.type == model.Account.AccountType.ASSET)
            ys_list = []
            labels = []
            for acc in accounts:
                labels.append(acc.name)
                ys_list.append(get_account_plot(acc.iban, xs))
            pyplot.stackplot(xs, ys_list, labels=labels)
            pyplot.legend(loc='upper left')
    else:
        ys = get_account_plot(args.iban, xs)
        pyplot.plot(list(map(lambda a: -a, reversed(xs))), list(reversed(ys)))

    pyplot.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    import_parser = subparsers.add_parser('import', help='Import transactions from your bank accounts')
    import_parser.add_argument('blz', help='The BLZ (Bankleitzahl/Bank identification number) of your bank')
    import_parser.add_argument('login', help='Your login/user name to your online banking account')
    import_parser.set_defaults(func=import_cmd)

    plot_parser = subparsers.add_parser('plot', help='Show saldo graph')
    plot_parser.add_argument('iban', help='The iban of your account')
    plot_parser.add_argument('days', type=int, help='How many days into the past the graph should be constructed')
    plot_parser.set_defaults(func=plot_cmd)

    arguments = parser.parse_args()
    arguments.func(arguments)







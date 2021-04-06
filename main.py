import logging
import sys
from fints.client import FinTS3PinTanClient
import fints_url
from getpass import getpass
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from banking import model
from datetime import date, timedelta, datetime
import math


logging.basicConfig(level=logging.INFO)


def find_account_name(iban, info):
    name = info['bank']['name'] + ' - '
    for acc in info['accounts']:
        if acc['iban'] == iban:
            name += f"{' '.join(acc['owner_name'])} ({acc['product_name']})"
            return name

    return name + "Account"


def test(blz: str, login: str, password: str):

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
                start_date = date.today() - timedelta(days=7)
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


if __name__ == '__main__':
    print(sys.argv)
    pw = getpass('Please enter your Bank password: ')
    db_engine = sqlalchemy.create_engine('sqlite+pysqlite:///db/testing.db', echo=True, future=True)
    Session = sessionmaker(db_engine)
    model.set_up(db_engine)
    test(sys.argv[1], sys.argv[2], pw)



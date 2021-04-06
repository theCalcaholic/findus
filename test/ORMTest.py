import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from banking import model
from datetime import datetime

class ORMTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.engine = None
        self.Session = None
        super(ORMTest, self).__init__(*args, **kwargs)

    @property
    def db_engine(self):
        if self._engine is not None:
            return self._engine
        else:
            return create_engine('sqlite+pysqlite:///:memory:', echo=True, future=True)

    def setUp(self) -> None:
        self._engine = None
        engine = self.db_engine
        self.Session = sessionmaker(engine)
        with self.Session():
            model.set_up(engine)

    def testModelInitializedSuccessfully(self) -> None:
        pass

    def testCreateAccount(self) -> None:
        with self.Session() as session:
            acc1 = model.Account(type=model.Account.AccountType.ASSET, balance=5.0, name='Test Account 1')
            session.add(acc1)
            session.commit()

            # Check dynamic object fields
            self.assertEqual(None, acc1.history_start)
            self.assertEqual(None, acc1.history_end)
            self.assertEqual(True, acc1.is_owned)
            self.assertEqual(5.0, acc1.start_balance)

            # Check dynamic queries
            # self.assertEqual(session.execute(select(model.Account.history_start)), None)
            # self.assertEqual(session.execute(select(model.Account.history_end)).first(), None)
            self.assertEqual(True, session.execute(select(model.Account.is_owned)).first()[0])
            self.assertEqual(5.0, session.execute(select(model.Account.start_balance)).first()[0])

    def testCreateTransaction(self) -> None:
        with self.Session() as session:
            acc1 = model.Account(type=model.Account.AccountType.ASSET, balance=5.0, name='Test Account 1')
            acc2 = model.Account(type=model.Account.AccountType.FOREIGN, balance=0.0, name='Test Account 2')
            session.add(acc1)
            session.add(acc2)
            session.commit()

            transaction1 = model.Transaction(source=acc1, target=acc2, amount=3.0, time=datetime.now(), message='test')

            session.add(transaction1)
            session.commit()

            self.assertEqual(1, len(acc1.transactions))
            print(f'transactions: {acc1.transactions}')
            print(f'withdrawals: {acc1.withdrawals}')
            print(f'deposits: {acc1.deposits}')
            self.assertEqual(1, len(acc1.withdrawals))
            self.assertEqual(0, len(acc1.deposits))

            self.assertEqual(-3.0, acc1._transactions_sum)
            self.assertEqual(3.0, acc2._transactions_sum)
            self.assertEqual(False, transaction1.is_transfer)




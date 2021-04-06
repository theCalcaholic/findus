from mt940.models import Balance as mt940_Balance, Transaction as mt940_Transaction, Amount as mt940_Amount, \
    DateTime as mt940_DateTime
from typing import Union, List, Tuple
import math
from enum import Enum
from datetime import datetime, timedelta
from banking.model.orm_base import mapper_registry
from banking.model.Transaction import Transaction
from sqlalchemy import Column, ForeignKey, String, Integer, DateTime, Float
from sqlalchemy.orm import relationship, column_property
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import select, or_, Enum as SqlEnum
from sqlalchemy.sql import case, func


@mapper_registry.mapped
class Account:
    class AccountType(Enum):
        ASSET = 1
        FOREIGN = 2

    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    iban = Column(String, unique=True, nullable=True)
    bic = Column(String)
    blz = Column(String)
    number = Column(String)
    type = Column(SqlEnum(AccountType), nullable=False)
    balance = Column(Float, nullable=True)
    name = Column(String)
    # deposits = relationship(Transaction, back_populates='target', order_by='Transaction.time')
    # withdrawals = relationship(Transaction, back_populates='source')
    # transactions = column_property(select([Transaction]).where(or_(Transaction.target == id, Transaction.source == id)),
    #                                order_by=Transaction.time)
    transactions = relationship(Transaction, primaryjoin='or_(Account.id == Transaction.target_id,'
                                                         ' Account.id == Transaction.source_id)', viewonly=True)
    transaction_times = association_proxy('transactions', 'time')
    # history_start = column_property(transactions.first().time)
    # history_start = column_property(select(Transaction.time.label('history_start'))
    #                                 .where(or_(id == Transaction.source_id, id == Transaction.target_id))
    #                                 .order_by(Transaction.time.asc())
    #                                 .limit(1)
    #                                 .scalar())
    # history_end = column_property(transactions.last().time)

    @hybrid_property
    def history_start(self):
        # if len(self.transactions) == 0:
        #     return None
        # return self.transactions[0].time
        return [*self.transaction_times, None][0]

    @history_start.expression
    def history_start(cls):
        raise NotImplementedError('Please initialize the object first!')
        # return case([(func.count(cls.transactions) > 0, )], else_=None)
        # return case([func.count(cls.transactions) > 0,  cls.transactions.first().time], else_=None)
        # return select([Transaction.time.label('history_start')])\
        #     .where(or_(cls.id == Transaction.source_id, cls.id == Transaction.target_id))\
        #     .order_by(Transaction.time.asc())\
        #     .limit(1)\
        #     .scalar()

    @hybrid_property
    def history_end(self):
        # if len(self.transactions) == 0:
        #     return None
        # return self.transactions[-1].time

        return [None, *self.transaction_times][-1]

    @history_end.expression
    def history_end(cls):
        raise NotImplementedError('Please initialize the object first!')
    #     return case([func.count(cls.transactions) > 0, cls.transactions.last().time], else_=None)

    @hybrid_property
    def _transactions_sum(self) -> float:
        # deposits = [] if self.deposits is None else self.deposits
        # withdrawals = [] if self.withdrawals is None else self.withdrawals
        d_sum = [] if self.deposits is None else sum([d.amount for d in self.deposits])
        w_sum = [] if self.withdrawals is None else sum([d.amount for d in self.withdrawals])
        return d_sum - w_sum

    @_transactions_sum.expression
    def _transactions_sum(cls) -> float:
        d_sum = select(func.sum(Transaction.amount))\
            .where(Transaction.target_id == cls.id)\
            .as_scalar()
        w_sum = select(func.sum(Transaction.amount))\
            .where(Transaction.source_id == cls.id)\
            .as_scalar()
        return select(case([(func.count(d_sum) == 0, 0.0)], else_=d_sum) -
                      case([(func.count(w_sum) == 0, 0.0)], else_=w_sum))

    @hybrid_property
    def deposits(self):
        return [trans for trans in self.transactions if trans.target_id == self.id]

    @deposits.expression
    def deposits(cls):
        return select(cls.transactions).where(Transaction.target_id == cls.id)

    @hybrid_property
    def withdrawals(self):
        for trans in self.transactions:
            print(f'{self.id} =? {trans.source_id}')
        return [trans for trans in self.transactions if trans.source_id == self.id]

    @withdrawals.expression
    def withdrawals(cls):
        print("WITHDRAWALS EXPR")
        return select(cls.transactions).where(Transaction.source_id == cls.id)

    @hybrid_property
    def start_balance(self) -> float:
        return self.balance - self._transactions_sum

    @hybrid_property
    def is_owned(self) -> bool:
        return self.type in [Account.AccountType.ASSET]

    @is_owned.expression
    def is_owned(cls) -> bool:
        return cls.type.in_([Account.AccountType.ASSET])

    def __repr__(self):
        return f'Account(id={self.id!r}, iban={self.iban!r}, blz={self.blz!r}, bic={self.bic!r}, ' \
               f'number={self.number!r}, name={self.name!r}, balance={self.balance}, transactions={self.transactions!r}'

    # @property
    # def history_start(self):
    #     withdrawal_start = self.withdrawals.first().time
    #     deposit_start = self.deposits.first().time
    #     return deposit_start if deposit_start < withdrawal_start else withdrawal_start
    #
    # @property
    # def history_end(self):
    #     withdrawal_end = self.withdrawals.last().time
    #     deposit_end = self.deposits.last().time
    #     return deposit_end if deposit_end > withdrawal_end else withdrawal_end


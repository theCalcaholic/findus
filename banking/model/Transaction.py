from datetime import datetime
from banking.model import Account
from typing import Union
from banking.model.orm_base import mapper_registry
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, ForeignKeyConstraint
from sqlalchemy.orm import relationship


@mapper_registry.mapped
class Transaction:
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('account.id'), nullable=False)
    target_id = Column(Integer, ForeignKey('account.id'), nullable=False)
    source = relationship('Account', foreign_keys=[source_id])
    target = relationship('Account', foreign_keys=[target_id])
    amount = Column(Float, nullable=False)
    time = Column(DateTime, nullable=False)
    message = Column(String)

    source_fkc = ForeignKeyConstraint(['source_id'], ['source.id'])
    target_fkc = ForeignKeyConstraint(['target_id'], ['target.id'])

    # def __init__(self, *args, **kwargs):
    #     self.amount = 0.0
    #     super(Transaction, self).__init__(*args, **kwargs)

    @property
    def is_transfer(self):
        return self.source.is_owned and self.target.is_owned

    def __repr__(self):
        return f'Transaction(id={self.id!r}, source_id={self.source_id}, source={self.source!r}, target_id={self.target_id}, target={self.target!r}, amount={self.amount!r}, message={self.message}' \
               f'time={self.time!r})'


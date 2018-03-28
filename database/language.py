from sqlalchemy import String, Column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Language(Base):
    __tablename__ = 'language'
    iso_code = Column(String(6), primary_key=True)
    english_name = Column(String(100))
    malagasy_name = Column(String(100))
    language_ancestor = Column(String())
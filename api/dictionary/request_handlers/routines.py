async def save_changes_on_disk(app, session):
    if app["autocommit"]:
        try:
            session.commit()
            session.flush()
        except Exception:
            session.rollback()

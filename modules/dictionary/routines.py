async def save_changes_on_disk(app, session):
    session.commit()
    session.flush()
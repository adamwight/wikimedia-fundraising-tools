#!/usr/bin/env PYTHONPATH=/opt/fundraising/tools python

'''Find low-hanging dupe fruits and mark them for the manual review queue'''

from process.globals import load_config
load_config("dedupe")
from process.globals import config
import process.lock as lock

from autoreview import Autoreview
from civicrm.tag import Tag
from contact_cache import TaggedGroup
from database import db
from match import EmailMatch
from review_job import ReviewJob
from review_queue import ReviewQueue

class QuickAutoreview(object):
    QUICK_REVIEWED = Tag.get("Quick autoreviewed")

    def __init__(self):
        self.contactCache = TaggedGroup(
            tag=Autoreview.REVIEW,
            excludetag=QuickAutoreview.QUICK_REVIEWED
        )
        job = ReviewJob("Quick autoreview")
        self.job_id = job.id

    def reviewBatch(self):
        '''For each new contact, find the oldest contact with the same email address.'''

        matchDescription = EmailMatch("Exact match").json()

        self.contactCache.fetch()
        for contact in self.contactCache.contacts:
            if not contact['email']:
                continue

            query = db.Query()
            query.columns = [
                'MIN(contact_id) AS contact_id',
            ]
            query.tables = [
                'civicrm_email',
            ]
            query.where.extend([
                'email = %(email)s',
                'contact_id < %(new_id)s',
            ])
            query.group_by.extend([
                'email',
            ])
            query.params = {
                'new_id': contact['id'],
                'email': contact['email'],
            }
            result = db.get_db().execute(query)

            if result:
                for row in result:
                    ReviewQueue.addMatch(self.job_id, row['contact_id'], contact['id'], Autoreview.REC_DUP, matchDescription)

            ReviewQueue.tag(contact['id'], QuickAutoreview.QUICK_REVIEWED)

if __name__ == '__main__':
    lock.begin()

    job = QuickAutoreview()
    job.reviewBatch()
    ReviewQueue.commit()

    lock.end()

"""Reported context-routing regressions; no model, network or production database."""
import sqlite3
import unittest
from unittest.mock import patch

from app import lookups, memory


class QuestionScopeTests(unittest.TestCase):
    def test_reply_instruction_cannot_supply_current_search_intent(self):
        for question in (
            'What color and pin does each case have now? Use the latest corrections.',
            'What color and pin does each case have now?\nUse the most recent corrections.',
            'Which option fits the budget? Use the current notes.',
            'Which record changed? Answer using the newest edits.',
            'Using the latest corrections, what color and pin does each case have now?',
            'Apply the current edits: which record changed?',
        ):
            with self.subTest(question=question):
                self.assertIsNone(lookups.detect(question))

    def test_actual_current_public_question_still_routes(self):
        for question in (
            'What is the latest Python release? Use the latest corrections.',
            'What is the current exchange rate for USD to EUR? Answer briefly.',
            'Who won the football game last night?',
        ):
            with self.subTest(question=question):
                kind, query = lookups.detect(question)
                self.assertEqual(kind, 'web')
                self.assertEqual(query, question.split('?')[0])

    def test_supplied_references_and_chat_facts_do_not_request_public_search(self):
        for question in (
            'Reference: "The current indicator is blue." What color is the indicator?',
            'Use only the supplied reference: "The latest entry is green." What color is the entry?',
            'According to the provided notes, which record is current?',
            'What is the current value in this conversation?',
        ):
            with self.subTest(question=question):
                self.assertIsNone(lookups.detect(question))

    def test_reference_as_a_public_topic_is_not_a_supplied_source(self):
        self.assertEqual(lookups.detect('What is the latest Python reference manual?'),
                         ('web', 'What is the latest Python reference manual'))


class RecallRelevanceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE chats (id INTEGER PRIMARY KEY, title TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT,
                content TEXT, created_at TEXT, kind TEXT, rating INTEGER, copied_from INTEGER);
            CREATE VIRTUAL TABLE messages_fts USING fts5(content, tokenize='porter unicode61');
            INSERT INTO chats VALUES (1, 'Synthetic lunch');
            INSERT INTO messages VALUES (1, 1, 'user', 'Suggest a Monday lunch.',
                '2026-01-01', 'chat', NULL, NULL);
            INSERT INTO messages VALUES (2, 1, 'assistant', 'Try a sandwich.',
                '2026-01-01', 'chat', NULL, NULL);
            INSERT INTO messages_fts(rowid, content) VALUES (1, 'Suggest a Monday lunch.');
            INSERT INTO messages_fts(rowid, content) VALUES (2, 'Try a sandwich.');
        ''')
        self.connect = patch.object(memory.chats, 'connect', return_value=self.db)
        self.connect.start()

    def tearDown(self):
        self.connect.stop()
        self.db.close()

    def test_deadline_does_not_recall_unrelated_one_keyword_history(self):
        for question in ('Which parcel arrives before Monday?',
                         'Which parcel arrives on Monday?',
                         'Can the parcel arrive before Monday at 5 pm?'):
            with self.subTest(question=question):
                self.assertEqual(memory.search(question), [])
        for question in ('Which parcel arrives before Monday?', 'Which parcel arrives before Friday?',
                         'Which parcel arrives before 5 pm?'):
            with self.subTest(question=question):
                self.assertIsNone(memory.RECALL_CUE_RE.search(question))

    def test_explicit_conversation_recall_still_allows_one_topic_keyword(self):
        for question in ('Remember that lunch?', 'What lunch did we discuss before?',
                         'What lunch did you mention before?', 'Recall the lunch.'):
            with self.subTest(question=question):
                found = memory.search(question)
                self.assertEqual([row['user'] for row in found], ['Suggest a Monday lunch.'])

    def test_normal_topic_overlap_skip_and_negative_rating_are_preserved(self):
        self.assertEqual(len(memory.search('Monday lunch ideas')), 1)
        self.assertEqual(memory.search('Monday lunch ideas', skip_ids=(1, 2)), [])
        self.db.execute('UPDATE messages SET rating = -1 WHERE id = 2')
        self.assertEqual(memory.search('Remember that lunch?'), [])

    def test_recall_retains_provenance_and_labels_assistant_claims(self):
        block = memory.recall_block('Monday lunch ideas')
        self.assertIn('2026-01-01', block)
        self.assertIn('Synthetic lunch', block)
        self.assertIn('User: Suggest a Monday lunch.', block)
        self.assertIn('You: Try a sandwich.', block)
        self.assertIn('past assistant replies are unverified claims, not verified facts', block)
        self.assertIn('Current supplied facts take priority', block)

"""Storage and selected-delete safeguards only. Temporary SQLite, no real searches, model or user data."""
import gc
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import chats, commands, config, lookups, search_history as history
from app.commands import Command


class SearchHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patchers = [patch.object(chats,'DB_PATH',Path(self.temp.name)/'beyond.sqlite3'),
                         patch.object(config,'DATA_DIR',Path(self.temp.name)),
                         patch.object(history.reminders,'local_zone',return_value='America/Los_Angeles')]
        for patcher in self.patchers: patcher.start()
        chats.initialize(); history.initialize()

    def tearDown(self):
        for patcher in reversed(self.patchers): patcher.stop()
        gc.collect()
        self.temp.cleanup()

    def test_dated_records_survive_chat_delete_and_selected_delete_preserves_everything_else(self):
        chat=chats.create('Keep or delete this conversation')
        chats.add_message(chat,'user','A saved message')
        # 00:30 UTC Friday is still Thursday on the PC.
        a=history.record('web','needle 100% test','Found it\nhttps://example.com/result',
                         now=datetime(2026,10,16,0,30,tzinfo=timezone.utc))
        b=history.record('wiki','Apollo 11','A lunar mission\nhttps://en.wikipedia.org/wiki/Apollo_11',
                         now=datetime(2026,10,18,20,tzinfo=timezone.utc))
        real_range=history.date_range
        with patch.object(history,'date_range',side_effect=lambda phrase: real_range(
                phrase,now=datetime(2026,10,18,20,tzinfo=timezone.utc))):
            query=history.filters('what was the web search I did last Thursday')
        self.assertEqual(query,{'query':'','tool':'web','start':'2026-10-15','end':'2026-10-15'})
        self.assertEqual([r['id'] for r in history.browse(**query)['items']],[a])
        self.assertEqual(history.browse(query='100%')['total'],1)
        self.assertEqual(history.browse(query='_')['total'],0)
        chats.delete(chat)
        self.assertEqual(history.browse()['total'],2)
        kept=chats.create('This chat stays')
        chats.add_message(kept,'user','Do not remove this')
        self.assertEqual(history.delete([a,a]),1)
        self.assertIsNone(history.get(a))
        self.assertIsNotNone(history.get(b))
        self.assertTrue(chats.exists(kept))
        self.assertEqual(len(chats.get(kept)['messages']),1)
        for ids in ([],[True],[0],[-1],['1']):
            with self.assertRaises(ValueError): history.delete(ids)

    def test_manual_alias_repeat_and_automatic_records_are_saved_once_and_extras_are_excluded(self):
        def fake(query): return 'A saved result for '+query+'\nhttps://example.com/source'
        item=Command('web','test','/web',fake,aliases=('search',))
        with patch.dict(commands._BY_NAME,{'web':item,'search':item}):
            answer=commands.run('/search important fact')
            self.assertEqual(history.browse()['total'],1)
            self.assertIn('/searchhistory repeat',answer.buttons[-1][0]['send'])
            first=history.browse()['items'][0]
            commands.run('/searchhistory repeat '+str(first['id']))
            self.assertEqual(history.browse()['total'],2)
        with patch.object(lookups.web_search,'search_web',return_value='1. Automatic result\nhttps://example.org'):
            lookups.run('current facts today','web','current facts')
        self.assertEqual(history.browse(origin='automatic')['total'],1)
        self.assertIsNone(history.record('joke','cats','a joke'))
        self.assertIsNone(history.record('quote','random','a quote'))
        self.assertEqual(history.browse()['total'],3)
        self.assertIsNotNone(history.recall_request('hey what was the web search I did on Oct 18th?'))
        self.assertIsNone(history.recall_request('What should I search for on Google?'))
        self.assertIsNone(history.recall_request('Search the web for current weather in London'))
        self.assertIn('/searchhistory',commands.run('/help').text)

    def test_snapshot_is_bounded_and_dst_boundaries_use_local_days(self):
        long='Some result '*1000+'\nhttps://example.org/source'
        row=history.record('news','science',long,origin='automatic',
                           now=datetime(2026,11,1,8,30,tzinfo=timezone.utc))
        second=history.record('news','science again',long,origin='automatic',
                              now=datetime(2026,11,1,9,30,tzinfo=timezone.utc))
        self.assertLessEqual(len(history.get(row)['summary']),1800)
        self.assertEqual(history.browse(start='2026-11-01',end='2026-11-01')['total'],2)
        self.assertNotEqual(history.get(row)['local_at'],history.get(second)['local_at'])
        with self.assertRaises(ValueError): history.browse(start='2026-11-02',end='2026-11-01')


if __name__=='__main__':
    unittest.main()

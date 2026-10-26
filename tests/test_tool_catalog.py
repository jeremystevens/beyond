import re
import unittest
from pathlib import Path
from unittest.mock import patch
from app import commands, prompts


class ToolCatalogTests(unittest.TestCase):
    def test_inventory_names_every_registered_command_without_running_anything(self):
        with patch.object(commands, 'run') as run:
            catalog = prompts.command_catalog()
        self.assertEqual(set(re.findall(r'/([a-z][a-z0-9_]*)', catalog)), {c.name for c in commands.COMMANDS})
        self.assertLess(len(catalog), 2500)
        run.assert_not_called()

    def test_specific_usage_is_available_for_every_command_and_alias(self):
        for item in commands.COMMANDS:
            for name in (item.name, *item.aliases):
                with self.subTest(name=name):
                    text = prompts.tool_notes('How do I use /' + name + '?')
                    self.assertIn(item.summary, text)
                    self.assertIn(item.example, text)

    def test_new_registry_entries_are_included_without_another_prompt_list(self):
        item = commands.Command('futuretool', 'A future feature', '/futuretool example', lambda _: 'not called')
        with patch.object(commands, 'COMMANDS', [*commands.COMMANDS, item]):
            self.assertIn('/futuretool', prompts.command_catalog())

    def test_audit_has_an_explicit_path_for_every_registered_command(self):
        text = (Path(__file__).resolve().parents[1]/'planning/tool-routing-audit.md').read_text(encoding='utf-8')
        names = set(re.findall(r'^\| `/([a-z][a-z0-9_]*)` \|', text, re.M))
        self.assertEqual(names, {c.name for c in commands.COMMANDS})

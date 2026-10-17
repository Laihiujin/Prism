import unittest
from unittest.mock import Mock, patch
from fastapi_app.models.ip_pool import ProxyIP, IPStatus
from fastapi_app.services.ip_pool_service import IPPoolService


class IPBindingTests(unittest.TestCase):
    def setUp(self):
        self.service = IPPoolService.__new__(IPPoolService)
        self.service.ips = {}
        self.service._save_ips = Mock()
        self.manager = Mock()
        self.manager.get_account_binding.return_value = None
        self.patcher = patch('fastapi_app.services.ip_pool_service._get_cookie_manager', return_value=self.manager)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def node(self, node_id, **kwargs):
        node = ProxyIP(id=node_id, ip='fixture.invalid', port=8080, **kwargs)
        self.service.ips[node.id] = node
        return node

    def test_repeat_binding_is_idempotent_at_capacity(self):
        node = self.node('fixture', bound_account_ids=['account'], status=IPStatus.IN_USE)
        self.assertTrue(self.service.bind_account_to_ip(node.id, 'account'))
        self.assertEqual(node.bound_account_ids, ['account'])
        self.service._save_ips.assert_not_called()

    def test_bound_node_cannot_be_deleted(self):
        node = self.node('fixture', bound_account_ids=['account'])
        with self.assertRaises(ValueError):
            self.service.delete_ip(node.id)
        self.assertIn(node.id, self.service.ips)

    def test_unbind_keeps_failed_health(self):
        node = self.node('fixture', bound_account_ids=['account'], status=IPStatus.FAILED)
        self.service.unbind_account('account')
        self.assertEqual(node.status, IPStatus.FAILED)
        self.assertEqual(node.bound_account_ids, [])

    def test_auto_binding_skips_disabled_nodes(self):
        self.node('disabled', is_enabled=False)
        enabled = self.node('enabled')
        self.assertEqual(self.service.auto_bind_account('account').id, enabled.id)

    def test_failed_rebind_keeps_original_binding(self):
        original = self.node('original', bound_account_ids=['account'], status=IPStatus.IN_USE)
        self.node('full', bound_account_ids=['other'])
        with self.assertRaises(ValueError):
            self.service.bind_account_to_ip('full', 'account')
        self.assertEqual(original.bound_account_ids, ['account'])
        self.manager.set_account_binding.assert_not_called()

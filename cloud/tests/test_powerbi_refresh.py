"""Offline checks for refresh correlation and failure handling."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import refresh_powerbi as pbi


IDENTIFIER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
CONFIG = {name: IDENTIFIER for name in (
    "POWERBI_TENANT_ID", "POWERBI_CLIENT_ID", "POWERBI_WORKSPACE_ID", "POWERBI_DATASET_ID"
)}


class RefreshTests(unittest.TestCase):
    def test_configuration_rejects_missing_ids_before_network(self):
        with self.assertRaisesRegex(pbi.RefreshError, "POWERBI_TENANT_ID"):
            pbi.configuration({})

    @patch.object(pbi, "request_json")
    def test_oidc_exchanges_assertion_for_powerbi_scope(self, request):
        request.side_effect = [(200, {}, {"value": "assertion"}), (200, {}, {"access_token": "token"})]
        env = {"ACTIONS_ID_TOKEN_REQUEST_URL": "https://pipelines.actions.githubusercontent.com/token?x=1",
               "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "github-runtime-token"}
        self.assertEqual(pbi.access_token(CONFIG, env), "token")
        self.assertIn("audience=api%3A%2F%2FAzureADTokenExchange", request.call_args_list[0].args[0])
        self.assertEqual(request.call_args.kwargs["data"]["client_assertion"], "assertion")
        self.assertEqual(request.call_args.kwargs["data"]["scope"], "https://analysis.windows.net/powerbi/api/.default")

    @patch.object(pbi, "request_json")
    def test_waits_for_own_request_not_previous_success(self, request):
        request.side_effect = [
            (202, {"x-ms-request-id": IDENTIFIER}, {}),
            (200, {}, {"value": [{"requestId": OTHER, "status": "Completed"}]}),
            (200, {}, {"value": [{"requestId": IDENTIFIER, "status": "Unknown"}]}),
            (200, {}, {"value": [{"requestId": IDENTIFIER, "status": "Completed"}]}),
        ]
        sleep = Mock()
        self.assertEqual(pbi.refresh(CONFIG, "token", clock=lambda: 0, sleep=sleep), IDENTIFIER)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(sum("data" in c.kwargs for c in request.call_args_list), 1)

    @patch.object(pbi, "request_json")
    def test_failed_refresh_fails_pipeline(self, request):
        request.side_effect = [
            (202, {"Location": f"https://api.powerbi.com/refreshes/{IDENTIFIER}"}, {}),
            (200, {}, {"value": [{"requestId": IDENTIFIER, "status": "Failed"}]}),
        ]
        with self.assertRaisesRegex(pbi.RefreshError, "Failed"):
            pbi.refresh(CONFIG, "token")

    @patch.object(pbi, "request_json")
    def test_accepted_without_identifier_does_not_claim_success(self, request):
        request.return_value = (202, {}, {})
        with self.assertRaisesRegex(pbi.RefreshError, "without a request ID"):
            pbi.refresh(CONFIG, "token")
        self.assertEqual(request.call_count, 1)

    @patch.object(pbi, "request_json")
    def test_timeout_does_not_resubmit(self, request):
        request.side_effect = [(202, {"x-ms-request-id": IDENTIFIER}, {}), (200, {}, {"value": []})]
        clock = Mock(side_effect=[0, 0, 0, 2])
        with self.assertRaisesRegex(pbi.RefreshError, "Timed out"):
            pbi.refresh(CONFIG, "token", timeout=1, clock=clock, sleep=Mock())
        self.assertEqual(request.call_count, 2)

    @patch.object(pbi, "urlopen")
    def test_http_errors_hide_response_content_and_do_not_retry(self, open_url):
        open_url.side_effect = HTTPError("https://api.powerbi.com/", 403, "SECRET", {}, None)
        with self.assertRaises(pbi.RefreshError) as error:
            pbi.request_json("https://api.powerbi.com/", token="SECRET", data={})
        self.assertNotIn("SECRET", str(error.exception))
        self.assertEqual(open_url.call_count, 1)

    def test_workflow_refresh_depends_on_validated_build_and_opt_in(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/bigquery.yml").read_text()
        refresh_job = workflow.split("\n  powerbi:\n", 1)[1]
        self.assertIn("needs: historical", refresh_job)
        self.assertIn("needs.historical.result == 'success'", refresh_job)
        self.assertIn("vars.POWERBI_REFRESH_ENABLED == 'true'", refresh_job)


if __name__ == "__main__":
    unittest.main()

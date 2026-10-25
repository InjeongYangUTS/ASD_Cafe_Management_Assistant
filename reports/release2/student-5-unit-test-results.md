# Student 5 Unit Test Results

- Tested commit: `2fb9c0e`
- Tested at: 2026-10-25 14:00:22 +11:00
- Command: `py -m pytest student-5/tests -v`
- Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Kota\AppData\Local\Python\pythoncore-3.14-64\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Kota\OneDrive\Documents\UNI\ASD\ASD_Cafe_Management_Assistant
configfile: pyproject.toml
plugins: anyio-4.15.1, platformdirs-4.13.5
collecting ... collected 24 items

student-5/tests/test_backend_api.py::test_health_endpoint PASSED         [  4%]
student-5/tests/test_backend_api.py::test_list_payments PASSED           [  8%]
student-5/tests/test_backend_api.py::test_process_payment_successfully PASSED [ 12%]
student-5/tests/test_backend_api.py::test_rejects_invalid_payment_amount PASSED [ 16%]
student-5/tests/test_backend_api.py::test_rejects_unsupported_payment_method PASSED [ 20%]
student-5/tests/test_backend_api.py::test_mcp_catalogue_lists_student5_tools PASSED [ 25%]
student-5/tests/test_backend_api.py::test_mcp_route_returns_structured_tool_result PASSED [ 29%]
student-5/tests/test_backend_api.py::test_mcp_route_is_disabled_in_ci_mode PASSED [ 33%]
student-5/tests/test_backend_api.py::test_rag_route_returns_grounded_answer PASSED [ 37%]
student-5/tests/test_backend_api.py::test_rag_route_rejects_empty_question PASSED [ 41%]
student-5/tests/test_backend_api.py::test_rag_route_is_disabled_in_ci_mode PASSED [ 45%]
student-5/tests/test_backend_api.py::test_multi_agent_start_uses_anonymous_payment_evidence PASSED [ 50%]
student-5/tests/test_backend_api.py::test_multi_agent_get_proxies_shared_server_result PASSED [ 54%]
student-5/tests/test_backend_api.py::test_multi_agent_human_review_is_forwarded PASSED [ 58%]
student-5/tests/test_backend_api.py::test_multi_agent_route_is_disabled_in_cloud_mode PASSED [ 62%]
student-5/tests/test_backend_api.py::test_process_partial_refund_successfully PASSED [ 66%]
student-5/tests/test_backend_api.py::test_rejects_refund_above_remaining_amount PASSED [ 70%]
student-5/tests/test_backend_api.py::test_rejects_payment_that_does_not_match_order_total PASSED [ 75%]
student-5/tests/test_backend_api.py::test_payment_updates_student_4_order_status PASSED [ 79%]
student-5/tests/test_database_api.py::test_health_endpoint PASSED        [ 83%]
student-5/tests/test_database_api.py::test_create_and_read_payment PASSED [ 87%]
student-5/tests/test_database_api.py::test_update_payment PASSED         [ 91%]
student-5/tests/test_database_api.py::test_delete_payment PASSED         [ 95%]
student-5/tests/test_database_api.py::test_missing_required_fields PASSED [100%]

============================= 24 passed in 0.72s ==============================
```

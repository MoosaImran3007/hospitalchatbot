import json
import requests

from config import DIFY_REPORT_API_KEY, DIFY_REPORT_API_URL


def generate_assessment_report(
    user_id: str,
    questions_and_answers: list
):
    """
    Generate an assessment report using the Dify report workflow.

    Dify User Input expects:

    questions_and_answers = {
        "questions_and_answers": [
            {
                "question_id": "...",
                "question": "...",
                "answer": "..."
            }
        ]
    }
    """

    # ---------------------------------------------------------
    # 1. Validate configuration
    # ---------------------------------------------------------

    if not DIFY_REPORT_API_KEY:
        raise Exception("DIFY_REPORT_API_KEY is not configured")

    if not DIFY_REPORT_API_URL:
        raise Exception("DIFY_REPORT_API_URL is not configured")

    # ---------------------------------------------------------
    # 2. Validate input
    # ---------------------------------------------------------

    if not isinstance(questions_and_answers, list):
        raise Exception("questions_and_answers must be a list")

    if not questions_and_answers:
        raise Exception("questions_and_answers cannot be empty")

    # ---------------------------------------------------------
    # 3. Validate and preserve questionnaire data
    # ---------------------------------------------------------

    formatted_questions_and_answers = []

    for item in questions_and_answers:

        if not isinstance(item, dict):
            raise Exception(
                "Each question_and_answer item must be an object"
            )

        question_id = item.get("question_id")

        question = (
            item.get("question")
            or item.get("question_text")
        )

        answer = item.get("answer")

        if not question_id:
            raise Exception(
                f"Missing question_id in question_and_answer item: {item}"
            )

        if not question:
            raise Exception(
                f"Missing question in question_and_answer item: {item}"
            )

        if answer is None:
            raise Exception(
                f"Missing answer for question: {question}"
            )

        formatted_questions_and_answers.append({
            "question_id": str(question_id),
            "question": str(question),
            "answer": str(answer)
        })

    # ---------------------------------------------------------
    # 4. Build Dify request
    # ---------------------------------------------------------

    payload = {
        "inputs": {
            "questions_and_answers": {
                "questions_and_answers": formatted_questions_and_answers
            }
        },
        "response_mode": "blocking",
        "user": str(user_id)
    }

    headers = {
        "Authorization": f"Bearer {DIFY_REPORT_API_KEY}",
        "Content-Type": "application/json"
    }

    # ---------------------------------------------------------
    # DEBUG - See exactly what we send to Dify
    # ---------------------------------------------------------

    print("\n========== DIFY REQUEST ==========")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("==================================\n")

    # ---------------------------------------------------------
    # 5. Call Dify
    # ---------------------------------------------------------

    try:
        response = requests.post(
            DIFY_REPORT_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            raise Exception(
                f"Dify report generation failed "
                f"(HTTP {response.status_code}): "
                f"{response.text}"
            )

        data = response.json()

    except requests.Timeout:
        raise Exception(
            "Dify report generation timed out"
        )

    except requests.RequestException as e:
        raise Exception(
            f"Could not connect to Dify: {str(e)}"
        )

    except ValueError:
        raise Exception(
            "Dify returned an invalid JSON response"
        )

    # ---------------------------------------------------------
    # 6. Inspect Dify response
    # ---------------------------------------------------------

    print("\n========== DIFY RESPONSE ==========")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("===================================\n")

    # ---------------------------------------------------------
    # 7. Extract workflow outputs
    # ---------------------------------------------------------

    workflow_data = data.get("data", {})

    if not isinstance(workflow_data, dict):
        raise Exception(
            f"Invalid Dify workflow data: {workflow_data}"
        )

    outputs = workflow_data.get("outputs", {})

    if not isinstance(outputs, dict):
        raise Exception(
            f"Dify returned invalid outputs: {outputs}"
        )

    print("\n========== DIFY OUTPUTS ==========")
    print(json.dumps(outputs, indent=2, ensure_ascii=False))
    print("==================================\n")

    # ---------------------------------------------------------
    # 8. Find report output
    # ---------------------------------------------------------

    report = None

    # Most likely output names
    for key in ["text", "report", "answer", "result"]:
        if key in outputs and outputs[key] is not None:
            report = outputs[key]
            break

    if report is None:
        raise Exception(
            "Dify did not return a report. "
            f"Available output keys: {list(outputs.keys())}"
        )

    # ---------------------------------------------------------
    # 9. Parse report JSON if possible
    # ---------------------------------------------------------

    report_data = report

    if isinstance(report, str):

        cleaned_report = report.strip()

        # Remove Markdown JSON code fences
        if cleaned_report.startswith("```json"):
            cleaned_report = cleaned_report[7:].strip()

        elif cleaned_report.startswith("```"):
            cleaned_report = cleaned_report[3:].strip()

        if cleaned_report.endswith("```"):
            cleaned_report = cleaned_report[:-3].strip()

        try:
            report_data = json.loads(cleaned_report)

        except json.JSONDecodeError:
            # Keep plain text if Dify returned normal text
            report_data = report

    # ---------------------------------------------------------
    # 10. Return standardized result
    # ---------------------------------------------------------

    return {
        "report": report_data,
        "workflow_run_id": data.get("workflow_run_id")
    }
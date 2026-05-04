from collections.abc import AsyncGenerator
from typing import Any
import json
import re

import httpx

from app.core.config import Settings
from app.models.schemas.deal import DealRequest, DealResponse


class DealWorkflow:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def run(self, request: DealRequest) -> DealResponse:
        timeout = httpx.Timeout(
            connect=10.0,
            read=180.0,
            write=30.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            result: dict[str, Any] = {}

            if request.health_quadrant:
                result["health_quadrant"] = await self._call_health_quadrant(
                    client,
                    request.health_quadrant.model_dump(),
                )

            profile_body = None

            if request.customer_profile:
                profile_body = request.customer_profile.model_dump()
            elif request.customer_package:
                profile_body = {
                    "idCard": request.customer_package.idCard
                }

            if profile_body:
                result["customer_profile"] = await self._call_runtime_endpoint(
                    client,
                    endpoint_id="93c5ae184119efb7f010a382536451de",
                    body=profile_body,
                )

            if request.customer_package:
                result["customer_package"] = await self._call_runtime_endpoint(
                    client,
                    endpoint_id="a26040a548a406a0e99dea8239d8ac29",
                    body=request.customer_package.model_dump(),
                )

            result = self._stringify_quadrants(result)

            dify_result = await self._call_dify(client, request, result)
            result["dify"] = dify_result

        raw_answer = dify_result.get("answer") or ""
        clean_answer = self._clean_dify_answer(raw_answer)

        return DealResponse(
            deal_id=request.deal_id,
            content=clean_answer or "deal pipeline completed",
            result=result,
            sources=[],
        )

    async def stream(self, request: DealRequest) -> AsyncGenerator[str, None]:
        response = await self.run(request)
        yield f"data: {response.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    def _clean_dify_answer(self, answer: str) -> str:
        if "</think>" in answer:
            answer = answer.split("</think>", 1)[1]

        answer = answer.strip()

        answer = re.sub(
            r"^```json\s*",
            "",
            answer,
            flags=re.IGNORECASE,
        )

        answer = re.sub(
            r"^```\s*",
            "",
            answer,
        )

        answer = re.sub(
            r"\s*```$",
            "",
            answer,
        )

        return answer.strip()


    def _stringify_quadrants(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                if key == "quadrants" and isinstance(value, list):
                    obj[key] = json.dumps(value, ensure_ascii=False)
                else:
                    obj[key] = self._stringify_quadrants(value)
        elif isinstance(obj, list):
            return [self._stringify_quadrants(item) for item in obj]
        return obj

    async def _call_health_quadrant(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.settings.ai_platform_base_url}/health-quadrant"

        resp = await client.post(url, json=payload)

        print("HEALTH_URL:", url)
        print("HEALTH_PAYLOAD:", payload)
        print("HEALTH_STATUS:", resp.status_code)
        print("HEALTH_BODY:", resp.text)

        resp.raise_for_status()
        return resp.json()

    async def _call_runtime_endpoint(
        self,
        client: httpx.AsyncClient,
        endpoint_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.settings.ai_platform_base_url}/ui-builder/runtime/endpoints/{endpoint_id}/invoke"

        payload = {
            "flowNum": 1,
            "queryParams": {},
            "body": body,
            "createdBy": "",
        }

        headers = {
            "Content-Type": "application/json",
            "X-User-Id": "2",
        }

        resp = await client.post(url, json=payload, headers=headers)

        print("RUNTIME_URL:", url)
        print("RUNTIME_PAYLOAD:", payload)
        print("RUNTIME_HEADERS:", headers)
        print("RUNTIME_STATUS:", resp.status_code)
        print("RUNTIME_BODY:", resp.text)

        resp.raise_for_status()
        return resp.json()

    async def _call_dify(
        self,
        client: httpx.AsyncClient,
        request: DealRequest,
        upstream_result: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.settings.dify_base_url}/chat-messages"

        headers = {
            "Authorization": f"Bearer {self.settings.dify_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": {
                "deal_id": request.deal_id or "",
                "context": json.dumps(request.context or {}, ensure_ascii=False),
                "upstream_result": json.dumps(upstream_result or {}, ensure_ascii=False),
            },
            "query": request.message,
            "response_mode": "blocking",
            "user": request.user_id,
        }

        resp = await client.post(url, json=payload, headers=headers)

        print("DIFY_URL:", url)
        print("===== DIFY INPUT START =====")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("===== DIFY INPUT END =====")        
        print("DIFY_STATUS:", resp.status_code)
        print("DIFY_BODY:", resp.text)

        resp.raise_for_status()
        return resp.json()
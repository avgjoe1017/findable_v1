"""E2E test for calibration sample collection via API."""

import asyncio
import random
import string

import httpx

BASE_URL = "http://localhost:8000"


def random_email():
    return f"test_{''.join(random.choices(string.ascii_lowercase, k=8))}@example.com"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        email = random_email()
        password = "testpass123"

        print(f"1. Registering user: {email}")
        resp = await client.post(
            "/v1/auth/register",
            json={"email": email, "password": password, "name": "Calibration Tester"},
        )
        print(f"   Register status: {resp.status_code}")

        print("2. Logging in...")
        resp = await client.post(
            "/v1/auth/login",
            data={
                "username": email,
                "password": password,
            },
        )
        if resp.status_code != 200:
            print(f"   Login failed: {resp.status_code} - {resp.text}")
            return

        token_data = resp.json()
        access_token = token_data.get("access_token")
        print("   Login successful, got token")

        headers = {"Authorization": f"Bearer {access_token}"}

        # Use a simple, fast site for testing
        domain = "example.com"
        print(f"3. Creating site: {domain}")
        resp = await client.post(
            "/v1/sites", json={"domain": domain, "name": "Example Site"}, headers=headers
        )

        if resp.status_code != 201:
            print(f"   Site creation failed: {resp.status_code} - {resp.text}")
            return

        site_data = resp.json()
        site_id = site_data.get("data", {}).get("id") or site_data.get("id")
        print(f"   Site created: {site_id}")

        print("4. Starting audit with observation...")
        resp = await client.post(
            f"/v1/sites/{site_id}/runs",
            json={"include_observation": True, "include_benchmark": False},
            headers=headers,
        )

        if resp.status_code not in [200, 201, 202]:
            print(f"   Run creation failed: {resp.status_code} - {resp.text}")
            return

        run_data = resp.json()
        run_id = run_data.get("data", {}).get("id") or run_data.get("id")
        print(f"   Run started: {run_id}")

        # Poll for completion
        print("5. Polling for run completion...")
        max_polls = 120  # 4 minutes max
        poll_count = 0

        while poll_count < max_polls:
            resp = await client.get(f"/v1/runs/{run_id}", headers=headers)
            if resp.status_code == 200:
                run = resp.json().get("data", resp.json())
                status = run.get("status")
                progress = run.get("progress", {})
                current_step = progress.get("current_step", "unknown")

                print(f"   [{poll_count}] Status: {status} - Step: {current_step}")

                if status == "completed":
                    print("\n   Run completed successfully!")
                    break
                elif status == "failed":
                    print(f"\n   Run failed: {run.get('error_message')}")
                    return

            poll_count += 1
            await asyncio.sleep(2)

        if poll_count >= max_polls:
            print("\n   Timeout waiting for run completion")
            return

        # Check for calibration samples
        print("\n6. Checking calibration samples...")
        resp = await client.get(
            "/v1/calibration/samples", headers=headers, params={"run_id": run_id, "limit": 10}
        )

        if resp.status_code == 200:
            samples_data = resp.json()
            samples = samples_data.get("data", samples_data)
            if isinstance(samples, list):
                print(f"   Found {len(samples)} calibration samples!")
                for sample in samples[:3]:
                    print(f"   - Q: {sample.get('question_text', 'N/A')[:50]}...")
                    print(
                        f"     Sim: {sample.get('sim_answerability')} | Obs: mentioned={sample.get('obs_mentioned')}, cited={sample.get('obs_cited')}"
                    )
                    print(f"     Match: {sample.get('outcome_match')}")
            else:
                print(f"   Samples response: {samples}")
        else:
            print(f"   Failed to get samples: {resp.status_code} - {resp.text}")

        print("\n7. Checking calibration summary...")
        resp = await client.get("/v1/calibration/summary", headers=headers)
        if resp.status_code == 200:
            summary = resp.json().get("data", resp.json())
            print(f"   Total samples: {summary.get('total_samples', 0)}")
            print(f"   Accuracy: {summary.get('accuracy', 0):.1%}")

        print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(main())

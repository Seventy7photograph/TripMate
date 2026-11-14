// 文件说明：性能测试脚本：trip_crud。
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://host.docker.internal:8010/api/v1";

export const options = {
  scenarios: {
    trip_crud: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || "10s",
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

function tripPayload(index) {
  return JSON.stringify({
    brief: {
      destination: `Perf City ${index}`,
      origin: "Shanghai",
      start_date: "2026-12-01",
      end_date: "2026-12-03",
      party_size: 2,
      budget_minor: 500000,
      currency: "CNY",
      interests: ["food"],
      pace: "balanced",
      transport_preferences: [],
      lodging_preferences: [],
      must_visit: [],
      avoid: [],
      constraints: [],
    },
  });
}

function headers(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export function setup() {
  const email = `k6-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;
  const registration = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({
      email,
      password: "correct-horse-battery-staple",
      display_name: "k6 CRUD",
    }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(registration, {
    "performance user registered": (response) => response.status === 201,
  });
  return { token: registration.json("access_token") };
}

export default function (data) {
  const requestHeaders = headers(data.token);
  const unique = `${__VU}-${__ITER}-${Date.now()}`;

  const created = http.post(
    `${BASE_URL}/trips`,
    tripPayload(unique),
    { headers: requestHeaders, tags: { name: "trip_create" } },
  );
  const createOk = check(created, {
    "trip created": (response) => response.status === 201,
  });
  if (!createOk) return;
  const tripId = created.json("id");

  const listed = http.get(`${BASE_URL}/trips`, {
    headers: requestHeaders,
    tags: { name: "trip_list" },
  });
  check(listed, {
    "trip listed": (response) => response.status === 200,
  });

  const detail = http.get(`${BASE_URL}/trips/${tripId}`, {
    headers: requestHeaders,
    tags: { name: "trip_read" },
  });
  check(detail, {
    "trip read": (response) => response.status === 200,
  });

  const updated = http.patch(
    `${BASE_URL}/trips/${tripId}`,
    JSON.stringify({ expected_version: 1, status: "ready" }),
    { headers: requestHeaders, tags: { name: "trip_update" } },
  );
  check(updated, {
    "trip updated": (response) => response.status === 200,
  });

  const archived = http.del(
    `${BASE_URL}/trips/${tripId}?expected_version=2`,
    null,
    { headers: requestHeaders, tags: { name: "trip_delete" } },
  );
  check(archived, {
    "trip soft deleted": (response) => response.status === 204,
  });

  sleep(0.1);
}

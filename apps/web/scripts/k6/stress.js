/* eslint-disable import/no-anonymous-default-export */
import http from "k6/http";
import { check } from "k6";

export const options = {
  stages: [
    { duration: "1m", target: 100 },
    { duration: "1m", target: 300 },
    { duration: "1m", target: 500 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1500"],
  },
};

const BASE_URL = __ENV.BASE_URL ?? "http://localhost:3000";

export default function () {
  const response = http.get(`${BASE_URL}/connexion`);
  check(response, {
    "la page résiste au pic": (r) => r.status === 200,
  });
}

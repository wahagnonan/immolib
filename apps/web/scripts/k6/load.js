/* eslint-disable import/no-anonymous-default-export */
import http from "k6/http";
import { check } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "1m", target: 50 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

const BASE_URL = __ENV.BASE_URL ?? "http://localhost:3000";

export default function () {
  const response = http.get(`${BASE_URL}/connexion`);
  check(response, {
    "page d'accueil répond 200": (r) => r.status === 200,
  });
}

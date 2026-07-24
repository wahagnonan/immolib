import { ImageResponse } from "next/og";

export const size = {
  width: 512,
  height: 512,
};

export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "center",
          background: "#d4342b",
          borderRadius: 112,
          color: "white",
          display: "flex",
          height: "100%",
          justifyContent: "center",
          width: "100%",
        }}
      >
        <svg
          fill="none"
          height="360"
          viewBox="0 0 40 40"
          width="360"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M11.5 10.5V29.5"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="3.2"
          />
          <path
            d="M19 10.5V27.5C19 28.6 19.9 29.5 21 29.5H29"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.2"
          />
          <path
            d="M24.5 10.5H28.8V14.8"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2.6"
          />
        </svg>
      </div>
    ),
    size,
  );
}

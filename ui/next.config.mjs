/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker 배포용 자기완결 출력 (HF Space 단일 컨테이너) — dev 서버에는 영향 없음
  output: "standalone",
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
};

export default nextConfig;

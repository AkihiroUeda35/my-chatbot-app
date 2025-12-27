import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Default to localhost if BACKEND_URL is not set
    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

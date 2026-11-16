/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Browser requests stay same-origin; only the Next.js server knows API_ORIGIN.
    const origin = (process.env.API_ORIGIN || 'http://127.0.0.1:8000').replace(/\/$/, '');
    if (process.env.NODE_ENV === 'production' && !process.env.API_ORIGIN) {
      throw new Error('Set API_ORIGIN to the deployed Python API URL before building');
    }
    return [{ source: '/api/:path*', destination: `${origin}/api/:path*` }];
  },
};

export default nextConfig;

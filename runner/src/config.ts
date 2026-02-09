const config = {
  aws: {
    s3: {
      bucket: process.env.S3_BUCKET!,
    },
    region: 'us-east-1',
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
  },
  backend: {
    url: process.env.BACKEND_URL!,
    token: process.env.BACKEND_JWT!,
  }
};

export default config;

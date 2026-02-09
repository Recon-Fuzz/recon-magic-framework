# runner


## DEMO / DEV

```bash
npx ts-node src/samples.ts # creates a job on the supabase db
```

```bash
yarn start --job-id $JOB_ID --url $GITHUB_URL # loads from that job # alternatively, build docker and run the container
```  

To test the Docker container locally:

Build with your choice of commands/args:  

```bash
docker build --build-arg NPM_TOKEN=$NPM_TOKEN --pull --rm -f "Dockerfile" -t runner:latest "."     
```

Run with:  

```bash
 docker run --env-file .env runner:latest --runner --job-id $JOB_ID --url $GITHUB_URL
```

Make sure your `.env` file is set up correctly. See `.env.example`

## Mac Silicon

Just add the flag `--platform linux/amd64`

This will use Rosetta to emulate amd64

Build:

```bash
docker build --build-arg NPM_TOKEN=$NPM_TOKEN --platform linux/amd64 -t recon-runner .
```


Run:

```bash
docker run -it --platform linux/amd64 --entrypoint /bin/bash --rm -v $PWD:/code recon-runner
```

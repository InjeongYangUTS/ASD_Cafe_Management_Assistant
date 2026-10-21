# AWS EC2 deployment baseline

This deployment runs the integrated cafe application on one Ubuntu EC2
instance with Docker Compose. It deliberately disables Ollama, MCP, RAG and
Multi-Agent for the required cloud baseline. The Multi-Agent container remains
available through the optional `ai` profile and is not started by the commands
below.

## 1. EC2 instance

Use the school AWS account. Select `ap-southeast-2` (Sydney) when the lab
allows it; otherwise use the region permitted by the lab and document that
choice. Recommended minimums:

- Ubuntu Server 24.04 LTS
- `t3.medium` (4 GiB); use `t3.large` if the lab permits and builds run out of memory
- 30 GiB gp3 storage
- Auto-assign public IPv4 enabled

Security-group inbound rules:

| Port | Source | Purpose |
|---:|---|---|
| 22 | Your current public IP `/32` only | SSH |
| 5100 | Assessment/tester IPs | Shared application |
| 5110 | Assessment/tester IPs | Student 1 frontend |
| 5200 | Assessment/tester IPs | Student 2 frontend |
| 5201 | Assessment/tester IPs | Student 2 browser API |
| 5300 | Assessment/tester IPs | Student 3 frontend |
| 5400 | Assessment/tester IPs | Student 4 frontend |
| 5500 | Assessment/tester IPs | Student 5 frontend |

Do not open database ports `7100`, `7300`, `7400`, `7500` or backend ports
`8100`, `8300`, `8400`, `8500`. Docker may publish them on the instance, but
the AWS security group must block them from the internet.

## 2. Prepare the instance

Copy `deploy/aws/setup-ec2.sh` to the instance or clone the repository, then:

```bash
chmod +x deploy/aws/*.sh
./deploy/aws/setup-ec2.sh
```

Sign out and reconnect after the script finishes.

## 3. Configure and deploy

Clone the repository and switch to the approved deployment branch:

```bash
git clone https://github.com/InjeongYangUTS/ASD_Cafe_Management_Assistant.git
cd ASD_Cafe_Management_Assistant
git switch release2-cloud-deployment
cp .env.cloud.example .env.cloud
```

Generate the session secret:

```bash
openssl rand -hex 32
```

Edit `.env.cloud`, paste that output as `SHARED_SECRET_KEY`, and set
`PUBLIC_HOST` to the EC2 public IPv4 address or public DNS name. Never commit
`.env.cloud`.

Deploy:

```bash
chmod +x deploy/aws/*.sh
./deploy/aws/deploy.sh
```

Open `http://EC2_PUBLIC_ADDRESS:5100` and test registration, login and the five
feature links. From another computer, run:

```bash
./deploy/aws/smoke-test.sh EC2_PUBLIC_ADDRESS
```

## 4. Evidence

Capture:

1. EC2 instance summary with state `Running` and no credentials visible.
2. Security-group rules.
3. `docker compose ... ps` showing healthy/running core containers and no
   Multi-Agent container.
4. Shared application opened through the EC2 public address.
5. One create/read/update/delete flow covering each student feature.
6. Persistent data still present after `docker compose ... restart`.

## 5. Stop or remove resources

Stop the EC2 instance when it is not being assessed. To remove only the
containers while retaining named database volumes:

```bash
docker compose --env-file .env.cloud \
  -f docker-compose.yml -f docker-compose.cloud.yml down
```

Do not add `-v` unless the database data is intentionally being deleted.

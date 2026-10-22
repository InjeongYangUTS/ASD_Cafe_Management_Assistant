# Azure VM Cloud Deployment

This guide deploys the Cafe Management Assistant to a Microsoft Azure Ubuntu
virtual machine using Docker Compose. The required cloud baseline runs the
shared frontend and all five student microservice groups. Local AI services
such as Ollama, MCP, RAG and Multi-Agent are intentionally excluded from the
cloud baseline.

## 1. Azure virtual machine

The validated deployment used:

- Microsoft Azure Virtual Machine
- Ubuntu Server 24.04 LTS
- Standard B2s v2
- 2 vCPUs and 8 GiB RAM
- Public IPv4 enabled
- SSH public-key authentication
- Docker Engine and Docker Compose

## 2. Network security rules

Restrict all permitted ports to the current tester or administrator IP
address.

| Port | Purpose |
|---:|---|
| 22 | SSH administration |
| 5100 | Shared application frontend |
| 5110 | Student 1 frontend |
| 5200 | Student 2 frontend |
| 5201 | Student 2 browser API |
| 5300 | Student 3 frontend |
| 5400 | Student 4 frontend |
| 5500 | Student 5 frontend |
| 8500 | Student 5 browser API |

Port 8500 is currently required because the Student 5 static frontend sends
browser requests directly to its backend. It must remain restricted to the
approved tester IP. A future reverse-proxy improvement should remove the need
to expose this backend port.

Database ports and all other backend ports must not be exposed publicly.
Unnecessary default rules, including port 80 when unused, should be removed.

## 3. Prepare the VM

Connect using the Azure VM SSH private key:

```bash
ssh -i /path/to/private-key.pem azureuser@AZURE_PUBLIC_IP
# Dynatrace Kubernetes Metrics Collector

Python tool to fetch Kubernetes deployment metrics (CPU, Memory, JVM Heap, Pod count) from Dynatrace SaaS API.

## Features

- List all deployments in a specific Kubernetes cluster and namespace
- Retrieve historical min/max CPU usage per deployment
- Retrieve historical min/max Memory usage per deployment
- Retrieve historical min/max JVM Heap memory usage (for Spring Boot microservices)
- Get pod count for each deployment
- Support for custom time ranges
- Output in table, JSON, or CSV format

## Prerequisites

- Python 3.7+
- Dynatrace SaaS account with API access
- API token with the following permissions:
  - `entities.read` - Read entities
  - `metrics.read` - Read metrics
  - `DataExport` or `WriteConfig` - Create dashboards (optional, only for dashboard creation)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Dynatrace credentials:
```bash
cp .env.example .env
```

3. Edit `.env` and add your Dynatrace details:
```
DYNATRACE_URL=https://your-environment-id.live.dynatrace.com
DYNATRACE_API_TOKEN=your_api_token_here
```

### Creating a Dynatrace API Token

1. Log in to your Dynatrace environment
2. Go to **Settings > Integration > Dynatrace API**
3. Click **Generate token**
4. Give it a name (e.g., "K8s Metrics Collector")
5. Enable the following permissions:
   - Read entities (`entities.read`)
   - Read metrics (`metrics.read`)
   - Write configuration (`WriteConfig`) - Optional, only if you want to create dashboards
6. Click **Generate** and copy the token to your `.env` file

## Usage

### Basic Usage

Fetch metrics for deployments in a specific cluster and namespace:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production
```

### Custom Time Range

Fetch metrics for the last 7 days:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production --hours 168
```

### JSON Output

Get results in JSON format:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production --format json
```

### CSV Output

Export results to a CSV file:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production --format csv
```

Or specify a custom output file:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production --format csv --output metrics.csv
```

If no output file is specified, the script will auto-generate a filename like `deployment_metrics_my-cluster_production_20231112_143052.csv`.

### Include JVM Heap Memory Metrics

For Spring Boot microservices, you can include JVM heap memory metrics using the `--include-heap` flag:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production --include-heap
```

Export to CSV with heap memory:

```bash
python get_deployment_metrics.py --cluster my-cluster --namespace production --format csv --include-heap --output metrics.csv
```

**Note:** JVM heap metrics require that Dynatrace OneAgent is monitoring your Java processes. If heap metrics are not available, the script will return 0 values for heap usage.

### Command Line Options

- `--cluster` (required): Kubernetes cluster name
- `--namespace` (required): Kubernetes namespace
- `--hours` (optional): Number of hours to look back for metrics (default: 24)
- `--format` (optional): Output format - 'table', 'json', or 'csv' (default: table)
- `--output` or `-o` (optional): Output file path for CSV format
- `--include-heap` (optional): Include JVM heap memory metrics for Spring Boot microservices

## Create Dynatrace Dashboard

You can automatically create a Dynatrace dashboard to visualize your deployment metrics directly in Dynatrace UI.

### Basic Dashboard Creation

Create a dashboard with CPU and Memory metrics:

```bash
python create_dashboard.py --cluster my-cluster --namespace production
```

### Dashboard with JVM Heap Metrics

Include JVM heap memory tiles in the dashboard:

```bash
python create_dashboard.py --cluster my-cluster --namespace production --include-heap
```

### What Gets Created

The script will:
- Create a new dashboard named "K8s Deployments - {cluster}/{namespace}"
- Add tiles for each deployment showing:
  - CPU usage over time (line chart)
  - Memory usage over time (line chart)
  - JVM Heap usage over time (line chart, if `--include-heap` is used)
- Set the default timeframe to last 2 hours
- Make the dashboard shareable

After creation, the script will output the dashboard URL which you can click to view in Dynatrace.

**Note:** Dashboard creation requires the `WriteConfig` permission on your API token.

## Output Example

### Table Format
```
====================================================================================================================
Deployment                     | Pods   | CPU Min         | CPU Max         | Memory Min      | Memory Max
====================================================================================================================
my-app-deployment              | 3      | 250.00 millicores | 1.25 cores    | 512.50 MB      | 1.20 GB
another-deployment             | 2      | 100.00 millicores | 800.00 millicores | 256.00 MB   | 768.00 MB
====================================================================================================================
```

### JSON Format
```json
[
  {
    "deployment_name": "my-app-deployment",
    "namespace": "production",
    "cluster": "my-cluster",
    "pod_count": 3,
    "cpu": {
      "min": 250.0,
      "max": 1250.0,
      "min_formatted": "250.00 millicores",
      "max_formatted": "1.25 cores"
    },
    "memory": {
      "min": 537395200,
      "max": 1288490188,
      "min_formatted": "512.50 MB",
      "max_formatted": "1.20 GB"
    }
  }
]
```

### CSV Format

**Without heap memory:**
```csv
cluster,deployment,cpu_usage_min,cpu_usage_max,memory_usage_min,memory_usage_max,number_of_pods
my-cluster,my-app-deployment,250.0,1250.0,537395200,1288490188,3
my-cluster,another-deployment,100.0,800.0,268435456,805306368,2
```

**With heap memory (using `--include-heap`):**
```csv
cluster,deployment,cpu_usage_min,cpu_usage_max,memory_usage_min,memory_usage_max,heap_usage_min,heap_usage_max,number_of_pods
my-cluster,my-app-deployment,250.0,1250.0,537395200,1288490188,268435456,536870912,3
my-cluster,another-deployment,100.0,800.0,268435456,805306368,134217728,402653184,2
```

The CSV file contains the following columns:
- `cluster`: Kubernetes cluster name
- `deployment`: Deployment name
- `cpu_usage_min`: Minimum CPU usage in millicores
- `cpu_usage_max`: Maximum CPU usage in millicores
- `memory_usage_min`: Minimum memory usage in bytes
- `memory_usage_max`: Maximum memory usage in bytes
- `heap_usage_min`: Minimum JVM heap usage in bytes (only when `--include-heap` is used)
- `heap_usage_max`: Maximum JVM heap usage in bytes (only when `--include-heap` is used)
- `number_of_pods`: Number of pods in the deployment

## Project Structure

```
dynatrace/
├── dynatrace_client.py       # Dynatrace API client library
├── get_deployment_metrics.py # Main script to fetch and export metrics
├── create_dashboard.py       # Script to create Dynatrace dashboards
├── example_usage.py          # Example code for programmatic usage
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
├── .env                      # Your credentials (not in git)
└── README.md                 # This file
```

## API Details

The tool uses the following Dynatrace API endpoints:

- `/api/v2/entities` - To list deployments, pods, and process groups
- `/api/v2/metrics/query` - To fetch CPU, memory, and JVM metrics
- `/api/config/v1/dashboards` - To create dashboards (used by `create_dashboard.py`)

Metrics used:
- `builtin:cloud.kubernetes.workload.cpu.usage` - CPU usage in millicores
- `builtin:cloud.kubernetes.workload.memory.usage` - Memory usage in bytes
- `builtin:tech.generic.mem.usedHeap` - JVM heap memory usage in bytes (when `--include-heap` is used)
- `builtin:tech.jvm.memory.pool.used` - Alternative JVM memory metric (fallback)

## Troubleshooting

### No deployments found

- Verify your cluster name and namespace are correct
- Check that Dynatrace is monitoring your Kubernetes cluster
- Ensure the cluster/namespace has deployments with the correct tags

### Authentication errors

- Verify your API token is correct
- Ensure the token has the required permissions
- Check that the Dynatrace URL is correct (no trailing slash)

### No metrics returned

- The deployment might be new (no historical data yet)
- Try increasing the `--hours` parameter
- Verify that metrics are being collected in Dynatrace UI

### Heap memory returns 0 or is not available

- Ensure Dynatrace OneAgent is installed and monitoring your pods
- Verify that your application is a Java/JVM-based application (e.g., Spring Boot)
- Check that the OneAgent has deep process monitoring enabled
- The process groups must be linked to the deployment/pods
- Wait a few minutes after deployment for metrics to start being collected
- Check in Dynatrace UI if JVM metrics are visible for your application

## License

MIT

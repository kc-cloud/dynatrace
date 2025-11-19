"""
Dynatrace API Client for Kubernetes monitoring
"""
import os
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json

class DynatraceClient:
    """Client for interacting with Dynatrace API"""

    def __init__(self, base_url: Optional[str] = None, api_token: Optional[str] = None):
        """
        Initialize Dynatrace client

        Args:
            base_url: Dynatrace environment URL (e.g., https://abc12345.live.dynatrace.com)
            api_token: API token with required permissions
        """
        load_dotenv()

        self.base_url = (base_url or os.getenv('DYNATRACE_URL', '')).rstrip('/')
        self.api_token = api_token or os.getenv('DYNATRACE_API_TOKEN', '')

        if not self.base_url or not self.api_token:
            raise ValueError("Dynatrace URL and API token must be provided")

        self.headers = {
            'Authorization': f'Api-Token {self.api_token}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make API request to Dynatrace

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}{endpoint}"

        try:
            print(f"DEBUG: Making request to: {url}")
            if params:
                print(f"DEBUG: Parameters: {params}")
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            print(f"DEBUG: Response status code: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            raise

    def _make_post_request(self, endpoint: str, data: Dict) -> Dict:
        """
        Make POST API request to Dynatrace

        Args:
            endpoint: API endpoint path
            data: JSON data to send

        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making POST request to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise

    def get_deployments(self, cluster_name: str, namespace: str) -> List[Dict]:
        """
        Get all deployments in a specific cluster and namespace

        Args:
            cluster_name: Kubernetes cluster name (e.g., "aks-nexus-deva")
            namespace: Kubernetes namespace

        Returns:
            List of deployment entities
        """
        # Since Dynatrace tags may have prefixes like "AKS Cluster: aks-nexus-deva",
        # we'll fetch all CLOUD_APPLICATION entities and filter manually
        print(f"DEBUG: Searching for deployments in cluster '{cluster_name}', namespace '{namespace}'")

        try:
            params = {
                # 'entitySelector': f'type("CLOUD_APPLICATION") AND tag("AKS Cluster:{cluster_name}")',
                'entitySelector': f'type("CLOUD_APPLICATION")',
                'fields': '+properties,+tags',
                'pageSize': 1000
            }

            response = self._make_request('/api/v2/entities', params=params)
            all_entities = response.get('entities', [])

            print(f"DEBUG: Retrieved {len(all_entities)} total CLOUD_APPLICATION entities")

            if not all_entities:
                print("WARNING: No CLOUD_APPLICATION entities found in your environment")
                return []

            # Filter by namespace and cloudApplicationDeploymentTypes containing KUBERNETES_DEPLOYMENT
            # (cluster is already filtered by the API selector)
            matched_entities = []

            for entity in all_entities:
                properties = entity.get('properties', {})
                deployment_types = properties.get('cloudApplicationDeploymentTypes', [])
                namespace_name = properties.get('namespaceName', '')

                # Check if namespace matches
                namespace_match = namespace.lower() in namespace_name.lower()

                # Check if KUBERNETES_DEPLOYMENT is in the deployment types list
                if namespace_match and 'KUBERNETES_DEPLOYMENT' in deployment_types:
                    matched_entities.append(entity)

            print(f"DEBUG: Found {len(matched_entities)} KUBERNETES_DEPLOYMENT entities in cluster '{cluster_name}' and namespace '{namespace}'")

            if matched_entities:
                # Print sample entity info for debugging
                sample = matched_entities[0]
                print(f"DEBUG: Sample entity - Name: {sample.get('displayName', 'N/A')}, ID: {sample.get('entityId', 'N/A')}")

                # Show the cluster tag for verification
                for tag in sample.get('tags', []):
                    tag_key = tag.get('key', '')
                    if 'cluster' in tag_key.lower():
                        tag_value = tag.get('value', tag.get('stringRepresentation', 'N/A'))
                        print(f"DEBUG: Cluster tag - {tag_key}: {tag_value}")
                        break
            with open('debug_deployments.json', 'w') as f:
                json.dump(all_entities, f, indent=2)
            return all_entities

        except Exception as e:
            print(f"ERROR: Failed to fetch deployments: {e}")
            return []

    def get_workload_metrics(
        self,
        deployment_entity_id: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        include_container_memory: bool = True
    ) -> Tuple[Dict[str, float], Dict[str, float], Optional[Dict[str, float]], int]:
        """
        Get CPU and Memory metrics for a deployment by aggregating pod metrics

        Args:
            deployment_entity_id: Dynatrace entity ID for the deployment
            time_from: Start time (default: 24 hours ago)
            time_to: End time (default: now)
            include_container_memory: Whether to include JVM heap memory metrics (default: False)

        Returns:
            Tuple of (cpu_metrics, memory_metrics, container_memory_metrics, pod_count)
            cpu_metrics: {'min': float, 'max': float} in millicores
            memory_metrics: {'min': float, 'max': float} in bytes
            container_memory_metrics: {'min': float, 'max': float} in bytes (None if include_container_memory=False)
            pod_count: number of pods
        """
        if not time_from:
            time_from = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')
        if not time_to:
            time_to = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        print(f"DEBUG: Getting metrics for deployment {deployment_entity_id}")

        # First, get all pods for this deployment
        pods = self._get_pods_for_deployment(deployment_entity_id)
        pod_count = len(pods)

        print(f"DEBUG: Found {pod_count} pods for deployment")

        if pod_count == 0:
            print("WARNING: No pods found for deployment")
            return {'min': 0.0, 'max': 0.0}, {'min': 0.0, 'max': 0.0}, None, 0

        # Aggregate metrics from all pods
        all_cpu_values = []
        all_memory_values = []

        for pod in pods:
            pod_id = pod.get('entityId', '')
            pod_name = pod.get('displayName', 'Unknown')

            print(f"DEBUG: Fetching metrics for pod: {pod_name} ({pod_id})")

            # Fetch CPU metrics for this pod
            cpu_metrics = self._get_metric_stats(
                metric_key='builtin:containers.cpu.usageMilliCores',
                entity_selector=f'entityId("{pod_id}")',
                time_from=time_from,
                time_to=time_to
            )

            # Fetch Memory metrics for this pod
            memory_metrics = self._get_metric_stats(
                metric_key='builtin:containers.memory.residentSetBytes',
                entity_selector=f'entityId("{pod_id}")',
                time_from=time_from,
                time_to=time_to
            )

            if cpu_metrics['min'] > 0 or cpu_metrics['max'] > 0:
                all_cpu_values.append(cpu_metrics)

            if memory_metrics['min'] > 0 or memory_metrics['max'] > 0:
                all_memory_values.append(memory_metrics)

        # Aggregate the metrics
        if all_cpu_values:
            aggregated_cpu = {
                'min': min(m['min'] for m in all_cpu_values if m['min'] > 0),
                'max': sum(m['max'] for m in all_cpu_values)  # Sum of max across all pods
            }
        else:
            aggregated_cpu = {'min': 0.0, 'max': 0.0}

        if all_memory_values:
            aggregated_memory = {
                'min': min(m['min'] for m in all_memory_values if m['min'] > 0),
                'max': sum(m['max'] for m in all_memory_values)  # Sum of max across all pods
            }
        else:
            aggregated_memory = {'min': 0.0, 'max': 0.0}

        # Fetch container memory metrics if requested
        container_memory_metrics = None
        if include_container_memory:
            container_memory_metrics = self._get_container_memory_metrics(
                deployment_entity_id=deployment_entity_id,
                time_from=time_from,
                time_to=time_to
            )

        print(f"DEBUG: Aggregated CPU: {aggregated_cpu}")
        print(f"DEBUG: Aggregated Memory: {aggregated_memory}")

        return aggregated_cpu, aggregated_memory, container_memory_metrics, pod_count

    def _get_metric_stats(
        self,
        metric_key: str,
        entity_selector: str,
        time_from: str,
        time_to: str
    ) -> Dict[str, float]:
        """
        Get min and max statistics for a metric

        Args:
            metric_key: Dynatrace metric key
            entity_selector: Entity selector query
            time_from: Start time
            time_to: End time

        Returns:
            Dictionary with 'min' and 'max' values
        """
        params = {
            'metricSelector': f'{metric_key}:min,{metric_key}:max',
            'entitySelector': entity_selector,
            'from': time_from,
            'to': time_to,
            'resolution': '1h'  # 1 hour resolution
        }

        try:
            print(f"DEBUG: Fetching metric {metric_key}")
            response = self._make_request('/api/v2/metrics/query', params=params)

            min_val = 0.0
            max_val = 0.0

            print(f"DEBUG: Metric response: {response}")

            if 'result' in response and len(response['result']) > 0:
                print(f"DEBUG: Found {len(response['result'])} result items")
                for result_item in response['result']:
                    metric_id = result_item.get('metricId', '')
                    data = result_item.get('data', [])

                    print(f"DEBUG: Metric ID: {metric_id}, Data entries: {len(data)}")

                    if data and len(data) > 0:
                        values = data[0].get('values', [])
                        print(f"DEBUG: Values count: {len(values)}, Sample: {values[:3] if len(values) > 0 else 'empty'}")
                        if values:
                            if ':min' in metric_id:
                                min_val = min([v for v in values if v is not None], default=0.0)
                            elif ':max' in metric_id:
                                max_val = max([v for v in values if v is not None], default=0.0)
            else:
                print(f"WARNING: No results returned for metric {metric_key}")
                if 'result' in response:
                    print(f"DEBUG: Empty result array")
                else:
                    print(f"DEBUG: No 'result' key in response")

            print(f"DEBUG: Final values for {metric_key} - min: {min_val}, max: {max_val}")
            return {'min': min_val, 'max': max_val}
        except Exception as e:
            print(f"ERROR: Error fetching metric {metric_key}: {e}")
            import traceback
            traceback.print_exc()
            return {'min': 0.0, 'max': 0.0}

    def _get_pods_for_deployment(self, deployment_entity_id: str) -> List[Dict]:
        """
        Get all pods (CONTAINER_GROUP_INSTANCE) for a deployment

        Args:
            deployment_entity_id: Deployment entity ID

        Returns:
            List of container group instance entities (pods)
        """
        # Query for container group instances (pods) belonging to this deployment
        # Using CONTAINER_GROUP_INSTANCE which is the entity type for pod metrics
        entity_selector = f'type("CONTAINER_GROUP_INSTANCE"),fromRelationships.isCgiOfCai(type("CLOUD_APPLICATION_INSTANCE"),fromRelationships.isInstanceOf(entityId("{deployment_entity_id}")))'

        params = {
            'entitySelector': entity_selector,
            'pageSize': 500,
            'fields': '+properties,+tags'
        }

        try:
            print(f"DEBUG: Fetching container group instances for deployment {deployment_entity_id}")
            response = self._make_request('/api/v2/entities', params=params)
            pods = response.get('entities', [])
            print(f"DEBUG: Found {len(pods)} container group instances")
            return pods
        except Exception as e:
            print(f"ERROR: Error fetching container group instances: {e}")
            return []

    def _get_pod_count(self, deployment_entity_id: str) -> int:
        """
        Get the number of pods for a deployment

        Args:
            deployment_entity_id: Deployment entity ID

        Returns:
            Number of pods
        """
        pods = self._get_pods_for_deployment(deployment_entity_id)
        return len(pods)

    def _get_container_memory_metrics(
        self,
        deployment_entity_id: str,
        time_from: str,
        time_to: str
    ) -> Dict[str, float]:
        """
        Get container memory metrics for a deployment.
        Since JVM heap metrics are unavailable in typical containerized workloads,
        this uses resident set bytes from CONTAINER_GROUP_INSTANCE as a substitute.

        Args:
            deployment_entity_id: Deployment entity ID
            time_from: Start time
            time_to: End time

        Returns:
            Dictionary with 'min' and 'max' memory values in bytes
        """
        # Get container group instances (pods) for this deployment
        pods = self._get_pods_for_deployment(deployment_entity_id)

        if not pods:
            print(f"No pods found for deployment {deployment_entity_id}")
            return {'min': 0.0, 'max': 0.0}

        min_mem = float('inf')
        max_mem = float('-inf')

        for pod in pods:
            container_id = pod['entityId']
            try:
                # Query container memory metrics
                metric_selector = (
                    f"builtin:containers.memory.residentSetBytes:min,"
                    f"builtin:containers.memory.residentSetBytes:max"
                )
                entity_selector = f'type("CONTAINER_GROUP_INSTANCE"),entityId("{container_id}")'

                response = self._query_metrics(
                    metric_selector=metric_selector,
                    entity_selector=entity_selector,
                    time_from=time_from,
                    time_to=time_to,
                    resolution='1h'
                )

                # Extract min/max from response
                for metric in response.get('result', []):
                    values = metric.get('data', [])[0].get('values', [])
                    values_filtered = [v for v in values if v is not None]
                    if not values_filtered:
                        continue

                    if metric['metricId'].endswith(':min'):
                        min_mem = min(min_mem, min(values_filtered))
                    elif metric['metricId'].endswith(':max'):
                        max_mem = max(max_mem, max(values_filtered))

            except Exception as e:
                print(f"Error fetching memory for container {container_id}: {e}")
                continue

        if min_mem == float('inf'):
            min_mem = 0.0
        if max_mem == float('-inf'):
            max_mem = 0.0

        return {'min': min_mem, 'max': max_mem}


    def create_dashboard(self, dashboard_config: Dict) -> Optional[str]:
        """
        Create a Dynatrace dashboard

        Args:
            dashboard_config: Dashboard configuration JSON

        Returns:
            Dashboard ID if successful, None otherwise
        """
        try:
            response = self._make_post_request('/api/config/v1/dashboards', dashboard_config)
            dashboard_id = response.get('id')
            return dashboard_id
        except Exception as e:
            print(f"Error creating dashboard: {e}")
            return None

    def _query_metrics(
        self,
        metric_selector: str,
        entity_selector: str = None,
        time_from: str = None,
        time_to: str = None,
        resolution: str = None
    ):
        """
        Generic helper to call /api/v2/metrics/query.
        Works with _make_request() which already returns parsed JSON.
        """

        params = {"metricSelector": metric_selector}

        if entity_selector:
            params["entitySelector"] = entity_selector
        if time_from:
            params["from"] = time_from
        if time_to:
            params["to"] = time_to
        if resolution:
            params["resolution"] = resolution

        # _make_request already:
        # - performs the HTTP call
        # - calls raise_for_status()
        # - returns response.json()
        return self._make_request("/api/v2/metrics/query", params=params)

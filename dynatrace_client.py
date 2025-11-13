"""
Dynatrace API Client for Kubernetes monitoring
"""
import os
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv


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
                'entitySelector': 'type("CLOUD_APPLICATION")',
                'fields': '+properties,+tags',
                'pageSize': 500
            }

            response = self._make_request('/api/v2/entities', params=params)
            all_entities = response.get('entities', [])

            print(f"DEBUG: Retrieved {len(all_entities)} total CLOUD_APPLICATION entities")

            if not all_entities:
                print("WARNING: No CLOUD_APPLICATION entities found in your environment")
                return []

            # Filter by cluster and namespace
            matched_entities = []
            cluster_only_matches = []
            has_any_namespace_tags = False

            for entity in all_entities:
                tags = entity.get('tags', [])
                properties = entity.get('properties', {})

                cluster_match = False
                namespace_match = False
                has_namespace_tag = False
                cluster_tag_info = None
                namespace_tag_info = None

                # Check tags for cluster and namespace
                for tag in tags:
                    tag_key = tag.get('key', '')
                    tag_value = str(tag.get('value', tag.get('stringRepresentation', '')))

                    # Check for cluster match (case-insensitive, handles prefixes like "AKS Cluster: ")
                    if 'cluster' in tag_key.lower():
                        cluster_tag_info = f"{tag_key}={tag_value}"
                        # Match if cluster_name appears in the tag value
                        if cluster_name.lower() in tag_value.lower():
                            cluster_match = True

                    # Check for namespace match (flexible - substring match)
                    if 'namespace' in tag_key.lower():
                        has_namespace_tag = True
                        has_any_namespace_tags = True
                        namespace_tag_info = f"{tag_key}={tag_value}"
                        # Match if namespace appears in the tag value
                        if namespace.lower() in tag_value.lower():
                            namespace_match = True

                # Also check properties for namespace (common in Dynatrace)
                for prop_key, prop_value in properties.items():
                    if 'namespace' in prop_key.lower():
                        has_namespace_tag = True
                        has_any_namespace_tags = True
                        if namespace_tag_info is None:
                            namespace_tag_info = f"property:{prop_key}={prop_value}"
                        # Match if namespace appears in the property value
                        if namespace.lower() in str(prop_value).lower():
                            namespace_match = True

                # Track entities that match cluster (for debugging)
                if cluster_match:
                    cluster_only_matches.append({
                        'name': entity.get('displayName', 'N/A'),
                        'entity': entity,
                        'cluster_tag': cluster_tag_info,
                        'namespace_tag': namespace_tag_info,
                        'has_namespace_tag': has_namespace_tag,
                        'namespace_match': namespace_match
                    })

                # Add entity if both cluster and namespace match
                if cluster_match and namespace_match:
                    matched_entities.append(entity)

            # If namespace tags don't exist, return all entities that match the cluster
            if not has_any_namespace_tags and len(cluster_only_matches) > 0:
                print(f"WARNING: No namespace tags found on any entities in this environment")
                print(f"INFO: Returning all {len(cluster_only_matches)} deployments for cluster '{cluster_name}'")
                print("INFO: You may need to filter by namespace manually based on deployment names")
                matched_entities = [match['entity'] for match in cluster_only_matches]

            print(f"DEBUG: Found {len(matched_entities)} deployments matching cluster '{cluster_name}'" +
                  (f" and namespace '{namespace}'" if has_any_namespace_tags else ""))

            # If no matches but we have cluster matches, show debug info
            if len(matched_entities) == 0 and len(cluster_only_matches) > 0:
                print(f"\nDEBUG: Found {len(cluster_only_matches)} entities matching cluster '{cluster_name}' but not namespace '{namespace}':")
                print("DEBUG: Here are the namespace tags for these entities:")
                for match in cluster_only_matches[:10]:  # Show first 10
                    print(f"  - {match['name']}")
                    print(f"    Cluster: {match['cluster_tag']}")
                    print(f"    Namespace: {match['namespace_tag'] if match['has_namespace_tag'] else 'No namespace tag'}")
                    print()

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

            return matched_entities

        except Exception as e:
            print(f"ERROR: Failed to fetch deployments: {e}")
            return []

    def get_workload_metrics(
        self,
        deployment_entity_id: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        include_heap: bool = False
    ) -> Tuple[Dict[str, float], Dict[str, float], Optional[Dict[str, float]], int]:
        """
        Get CPU and Memory metrics for a deployment by aggregating pod metrics

        Args:
            deployment_entity_id: Dynatrace entity ID for the deployment
            time_from: Start time (default: 24 hours ago)
            time_to: End time (default: now)
            include_heap: Whether to include JVM heap memory metrics (default: False)

        Returns:
            Tuple of (cpu_metrics, memory_metrics, heap_metrics, pod_count)
            cpu_metrics: {'min': float, 'max': float} in millicores
            memory_metrics: {'min': float, 'max': float} in bytes
            heap_metrics: {'min': float, 'max': float} in bytes (None if include_heap=False)
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
                metric_key='builtin:cloud.kubernetes.workload.cpu.usage',
                entity_selector=f'entityId("{pod_id}")',
                time_from=time_from,
                time_to=time_to
            )

            # Fetch Memory metrics for this pod
            memory_metrics = self._get_metric_stats(
                metric_key='builtin:cloud.kubernetes.workload.memory.usage',
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

        # Fetch JVM heap metrics if requested
        heap_metrics = None
        if include_heap:
            heap_metrics = self._get_jvm_heap_metrics(
                deployment_entity_id=deployment_entity_id,
                time_from=time_from,
                time_to=time_to
            )

        print(f"DEBUG: Aggregated CPU: {aggregated_cpu}")
        print(f"DEBUG: Aggregated Memory: {aggregated_memory}")

        return aggregated_cpu, aggregated_memory, heap_metrics, pod_count

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
        Get all pods (CLOUD_APPLICATION_INSTANCE) for a deployment

        Args:
            deployment_entity_id: Deployment entity ID

        Returns:
            List of pod entities
        """
        # Query for pods belonging to this deployment
        entity_selector = f'type("CLOUD_APPLICATION_INSTANCE"),fromRelationships.isInstanceOf(entityId("{deployment_entity_id}"))'

        params = {
            'entitySelector': entity_selector,
            'pageSize': 500,
            'fields': '+properties,+tags'
        }

        try:
            print(f"DEBUG: Fetching pods for deployment {deployment_entity_id}")
            response = self._make_request('/api/v2/entities', params=params)
            pods = response.get('entities', [])
            print(f"DEBUG: Found {len(pods)} pods")
            return pods
        except Exception as e:
            print(f"ERROR: Error fetching pods: {e}")
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

    def _get_jvm_heap_metrics(
        self,
        deployment_entity_id: str,
        time_from: str,
        time_to: str
    ) -> Dict[str, float]:
        """
        Get JVM heap memory metrics for a deployment

        Args:
            deployment_entity_id: Deployment entity ID
            time_from: Start time
            time_to: End time

        Returns:
            Dictionary with 'min' and 'max' heap memory values in bytes
        """
        # Get process groups related to this deployment
        entity_selector = f'type("PROCESS_GROUP"),fromRelationships.runsOn(entityId("{deployment_entity_id}"))'

        params = {
            'entitySelector': entity_selector,
            'fields': '+properties'
        }

        try:
            response = self._make_request('/api/v2/entities', params=params)
            process_groups = response.get('entities', [])

            if not process_groups:
                # Try alternative relationship path via pods
                pod_selector = f'type("CLOUD_APPLICATION_INSTANCE"),fromRelationships.isInstanceOf(entityId("{deployment_entity_id}"))'
                pod_response = self._make_request('/api/v2/entities', params={'entitySelector': pod_selector})
                pods = pod_response.get('entities', [])

                if pods:
                    # Get process groups from pods
                    pod_ids = ','.join([f'"{pod["entityId"]}"' for pod in pods[:10]])  # Limit to first 10 pods
                    pg_selector = f'type("PROCESS_GROUP"),toRelationships.runsOn(entityId({pod_ids}))'
                    pg_response = self._make_request('/api/v2/entities', params={'entitySelector': pg_selector})
                    process_groups = pg_response.get('entities', [])

            if not process_groups:
                print(f"No process groups found for deployment {deployment_entity_id}")
                return {'min': 0.0, 'max': 0.0}

            # Aggregate heap metrics from all process groups
            all_heap_min = []
            all_heap_max = []

            for pg in process_groups:
                pg_id = pg.get('entityId', '')

                # Try to get JVM heap used metric
                heap_metrics = self._get_metric_stats(
                    metric_key='builtin:tech.generic.mem.usedHeap',
                    entity_selector=f'entityId("{pg_id}")',
                    time_from=time_from,
                    time_to=time_to
                )

                if heap_metrics['min'] > 0 or heap_metrics['max'] > 0:
                    all_heap_min.append(heap_metrics['min'])
                    all_heap_max.append(heap_metrics['max'])

            if not all_heap_min and not all_heap_max:
                # Try alternative JVM memory metrics
                for pg in process_groups:
                    pg_id = pg.get('entityId', '')
                    heap_metrics = self._get_metric_stats(
                        metric_key='builtin:tech.jvm.memory.pool.used',
                        entity_selector=f'entityId("{pg_id}")',
                        time_from=time_from,
                        time_to=time_to
                    )

                    if heap_metrics['min'] > 0 or heap_metrics['max'] > 0:
                        all_heap_min.append(heap_metrics['min'])
                        all_heap_max.append(heap_metrics['max'])

            if all_heap_min or all_heap_max:
                return {
                    'min': min(all_heap_min) if all_heap_min else 0.0,
                    'max': max(all_heap_max) if all_heap_max else 0.0
                }
            else:
                return {'min': 0.0, 'max': 0.0}

        except Exception as e:
            print(f"Error fetching JVM heap metrics: {e}")
            return {'min': 0.0, 'max': 0.0}

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

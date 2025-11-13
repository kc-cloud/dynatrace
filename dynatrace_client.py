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
            cluster_name: Kubernetes cluster name
            namespace: Kubernetes namespace

        Returns:
            List of deployment entities
        """
        # Try multiple entity types and tag formats as different Dynatrace versions use different conventions
        search_strategies = [
            # Strategy 1: CLOUD_APPLICATION with standard Kubernetes tags
            {
                'entity_type': 'CLOUD_APPLICATION',
                'tag_format': 'standard',
                'description': 'CLOUD_APPLICATION with [Kubernetes]cluster and [Kubernetes]namespace tags'
            },
            # Strategy 2: CLOUD_APPLICATION with alternative tag format (no brackets)
            {
                'entity_type': 'CLOUD_APPLICATION',
                'tag_format': 'no_brackets',
                'description': 'CLOUD_APPLICATION with Kubernetes:cluster and Kubernetes:namespace tags'
            },
            # Strategy 3: CLOUD_APPLICATION without namespace filter (then filter manually)
            {
                'entity_type': 'CLOUD_APPLICATION',
                'tag_format': 'cluster_only',
                'description': 'CLOUD_APPLICATION with cluster tag only'
            },
            # Strategy 4: Try without any filters to see all CLOUD_APPLICATION entities
            {
                'entity_type': 'CLOUD_APPLICATION',
                'tag_format': 'none',
                'description': 'CLOUD_APPLICATION without filters'
            }
        ]

        for strategy in search_strategies:
            try:
                entity_type = strategy['entity_type']
                tag_format = strategy['tag_format']
                print(f"DEBUG: Trying strategy: {strategy['description']}")

                # Build entity selector based on tag format
                if tag_format == 'standard':
                    entity_selector = (
                        f'type("{entity_type}"),'
                        f'tag("[Kubernetes]cluster:{cluster_name}"),'
                        f'tag("[Kubernetes]namespace:{namespace}")'
                    )
                elif tag_format == 'no_brackets':
                    entity_selector = (
                        f'type("{entity_type}"),'
                        f'tag("Kubernetes:cluster:{cluster_name}"),'
                        f'tag("Kubernetes:namespace:{namespace}")'
                    )
                elif tag_format == 'cluster_only':
                    entity_selector = (
                        f'type("{entity_type}"),'
                        f'tag("[Kubernetes]cluster:{cluster_name}")'
                    )
                else:  # none
                    entity_selector = f'type("{entity_type}")'

                params = {
                    'entitySelector': entity_selector,
                    'fields': '+properties,+tags',
                    'pageSize': 500
                }

                response = self._make_request('/api/v2/entities', params=params)
                entities = response.get('entities', [])

                print(f"DEBUG: Retrieved {len(entities)} entities")

                # If we used cluster_only or none, filter by namespace manually
                if tag_format in ['cluster_only', 'none'] and entities:
                    print(f"DEBUG: Filtering entities by namespace '{namespace}'")
                    filtered_entities = []
                    for entity in entities:
                        tags = entity.get('tags', [])
                        # Check if entity has the namespace tag
                        for tag in tags:
                            tag_key = tag.get('key', '')
                            tag_value = tag.get('value', tag.get('stringRepresentation', ''))

                            # Check various namespace tag formats
                            if (('[Kubernetes]namespace' in tag_key and namespace in str(tag_value)) or
                                ('Kubernetes:namespace' in tag_key and namespace in str(tag_value)) or
                                (tag_key == 'namespace' and namespace in str(tag_value))):
                                filtered_entities.append(entity)
                                break

                    entities = filtered_entities
                    print(f"DEBUG: After filtering: {len(entities)} entities match namespace '{namespace}'")

                if entities:
                    print(f"DEBUG: Successfully found {len(entities)} deployments using: {strategy['description']}")

                    # Print sample entity info for debugging
                    if entities:
                        sample = entities[0]
                        print(f"DEBUG: Sample entity - Name: {sample.get('displayName', 'N/A')}, ID: {sample.get('entityId', 'N/A')}")
                        print(f"DEBUG: Sample entity tags: {[tag.get('key', '') for tag in sample.get('tags', [])[:5]]}")

                    return entities

            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response'):
                    status_code = e.response.status_code
                    if status_code == 400:
                        print(f"DEBUG: Bad request (400) for strategy: {strategy['description']}")
                        continue
                    elif status_code == 404:
                        print(f"DEBUG: Not found (404) for strategy: {strategy['description']}")
                        continue
                    else:
                        print(f"DEBUG: HTTP error {status_code} for strategy: {strategy['description']}")
                        # For other HTTP errors, continue trying
                        continue
                else:
                    raise
            except Exception as e:
                print(f"DEBUG: Exception for strategy {strategy['description']}: {e}")
                continue

        # If we get here, none of the strategies worked
        print(f"WARNING: Could not find deployments for cluster '{cluster_name}' namespace '{namespace}' using any strategy")
        print(f"SUGGESTION: Run debug_entities.py to see available entity types and tags in your environment")
        return []

    def get_workload_metrics(
        self,
        deployment_entity_id: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        include_heap: bool = False
    ) -> Tuple[Dict[str, float], Dict[str, float], Optional[Dict[str, float]], int]:
        """
        Get CPU and Memory metrics for a deployment

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

        # Fetch CPU metrics
        cpu_metrics = self._get_metric_stats(
            metric_key='builtin:cloud.kubernetes.workload.cpu.usage',
            entity_selector=f'entityId("{deployment_entity_id}")',
            time_from=time_from,
            time_to=time_to
        )

        # Fetch Memory metrics
        memory_metrics = self._get_metric_stats(
            metric_key='builtin:cloud.kubernetes.workload.memory.usage',
            entity_selector=f'entityId("{deployment_entity_id}")',
            time_from=time_from,
            time_to=time_to
        )

        # Fetch JVM heap metrics if requested
        heap_metrics = None
        if include_heap:
            heap_metrics = self._get_jvm_heap_metrics(
                deployment_entity_id=deployment_entity_id,
                time_from=time_from,
                time_to=time_to
            )

        # Get pod count
        pod_count = self._get_pod_count(deployment_entity_id)

        return cpu_metrics, memory_metrics, heap_metrics, pod_count

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
            response = self._make_request('/api/v2/metrics/query', params=params)

            min_val = 0.0
            max_val = 0.0

            if 'result' in response and len(response['result']) > 0:
                for result_item in response['result']:
                    metric_id = result_item.get('metricId', '')
                    data = result_item.get('data', [])

                    if data and len(data) > 0:
                        values = data[0].get('values', [])
                        if values:
                            if ':min' in metric_id:
                                min_val = min([v for v in values if v is not None], default=0.0)
                            elif ':max' in metric_id:
                                max_val = max([v for v in values if v is not None], default=0.0)

            return {'min': min_val, 'max': max_val}
        except Exception as e:
            print(f"Error fetching metric {metric_key}: {e}")
            return {'min': 0.0, 'max': 0.0}

    def _get_pod_count(self, deployment_entity_id: str) -> int:
        """
        Get the number of pods for a deployment

        Args:
            deployment_entity_id: Deployment entity ID

        Returns:
            Number of pods
        """
        # Query for pods belonging to this deployment
        entity_selector = f'type("CLOUD_APPLICATION_INSTANCE"),fromRelationships.isInstanceOf(entityId("{deployment_entity_id}"))'

        params = {
            'entitySelector': entity_selector,
            'pageSize': 500
        }

        try:
            response = self._make_request('/api/v2/entities', params=params)
            return response.get('totalCount', 0)
        except Exception as e:
            print(f"Error fetching pod count: {e}")
            return 0

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

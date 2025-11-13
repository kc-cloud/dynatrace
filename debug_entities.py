"""
Debug script to discover available Dynatrace entity types and test API connectivity
"""
import argparse
from dynatrace_client import DynatraceClient
import requests


def test_api_connection(client: DynatraceClient):
    """Test basic API connectivity"""
    print("Testing API connection...")
    try:
        response = client._make_request('/api/v2/entityTypes')
        print("✓ API connection successful!\n")
        return response
    except Exception as e:
        print(f"✗ API connection failed: {e}\n")
        return None


def list_entity_types(client: DynatraceClient):
    """List all available entity types in the environment"""
    print("Fetching available entity types...")
    try:
        response = client._make_request('/api/v2/entityTypes')
        entity_types = response.get('types', [])

        print(f"\nFound {len(entity_types)} entity types:")
        print("=" * 80)

        # Filter for Kubernetes-related types
        k8s_types = [et for et in entity_types if 'CLOUD' in et or 'KUBERNETES' in et or 'WORKLOAD' in et or 'K8S' in et]

        if k8s_types:
            print("\nKubernetes/Cloud related entity types:")
            for entity_type in sorted(k8s_types):
                print(f"  - {entity_type}")

        print("\nAll entity types:")
        for entity_type in sorted(entity_types):
            print(f"  - {entity_type}")

        return entity_types
    except Exception as e:
        print(f"Error listing entity types: {e}")
        return []


def test_entity_query(client: DynatraceClient, entity_type: str, cluster: str = None, namespace: str = None):
    """Test querying a specific entity type"""
    print(f"\nTesting query for entity type: {entity_type}")
    print("-" * 80)

    try:
        # Build entity selector
        if cluster and namespace:
            entity_selector = (
                f'type("{entity_type}"),'
                f'tag("[Kubernetes]cluster:{cluster}"),'
                f'tag("[Kubernetes]namespace:{namespace}")'
            )
        elif cluster:
            entity_selector = f'type("{entity_type}"),tag("[Kubernetes]cluster:{cluster}")'
        else:
            entity_selector = f'type("{entity_type}")'

        params = {
            'entitySelector': entity_selector,
            'fields': '+properties,+tags',
            'pageSize': 10  # Limit results for testing
        }

        response = client._make_request('/api/v2/entities', params=params)
        entities = response.get('entities', [])
        total_count = response.get('totalCount', 0)

        print(f"✓ Query successful!")
        print(f"  Total entities: {total_count}")
        print(f"  Returned entities: {len(entities)}")

        if entities:
            print(f"\nFirst entity details:")
            entity = entities[0]
            print(f"  Display Name: {entity.get('displayName', 'N/A')}")
            print(f"  Entity ID: {entity.get('entityId', 'N/A')}")
            print(f"  Type: {entity.get('type', 'N/A')}")

            if 'tags' in entity:
                print(f"  All Tags:")
                for tag in entity.get('tags', []):
                    tag_key = tag.get('key', 'N/A')
                    tag_value = tag.get('value', tag.get('stringRepresentation', 'N/A'))
                    print(f"    - {tag_key}: {tag_value}")

            if 'properties' in entity:
                print(f"  Properties:")
                for prop_key, prop_value in entity.get('properties', {}).items():
                    print(f"    - {prop_key}: {prop_value}")

        return entities

    except requests.exceptions.HTTPError as e:
        if hasattr(e, 'response') and e.response.status_code == 404:
            print(f"✗ Entity type '{entity_type}' not found (404)")
        elif hasattr(e, 'response') and e.response.status_code == 400:
            print(f"✗ Bad request (400) - Entity type may not exist or invalid query")
            print(f"   Response: {e.response.text}")
        else:
            print(f"✗ Error querying entity type: {e}")
        return []
    except Exception as e:
        print(f"✗ Error: {e}")
        return []


def show_all_cloud_applications(client: DynatraceClient):
    """Show all CLOUD_APPLICATION entities and their tags to help identify correct naming"""
    print("\n" + "=" * 80)
    print("Fetching ALL CLOUD_APPLICATION entities to analyze tags...")
    print("=" * 80)

    try:
        params = {
            'entitySelector': 'type("CLOUD_APPLICATION")',
            'fields': '+properties,+tags',
            'pageSize': 50
        }

        response = client._make_request('/api/v2/entities', params=params)
        entities = response.get('entities', [])
        total_count = response.get('totalCount', 0)

        print(f"Found {total_count} CLOUD_APPLICATION entities (showing first {len(entities)})")

        if not entities:
            print("No CLOUD_APPLICATION entities found!")
            return

        # Collect all unique tag keys and some sample values
        all_tag_keys = set()
        cluster_tags = set()
        namespace_tags = set()

        for entity in entities:
            name = entity.get('displayName', 'N/A')
            tags = entity.get('tags', [])

            print(f"\n{'='*80}")
            print(f"Entity: {name}")
            print(f"Entity ID: {entity.get('entityId', 'N/A')}")
            print(f"Tags:")

            for tag in tags:
                tag_key = tag.get('key', 'N/A')
                tag_value = tag.get('value', tag.get('stringRepresentation', 'N/A'))
                all_tag_keys.add(tag_key)

                print(f"  - {tag_key}: {tag_value}")

                # Collect cluster and namespace tags
                if 'cluster' in tag_key.lower():
                    cluster_tags.add(f"{tag_key}={tag_value}")
                if 'namespace' in tag_key.lower():
                    namespace_tags.add(f"{tag_key}={tag_value}")

        print(f"\n{'='*80}")
        print("SUMMARY - All unique tag keys found:")
        print("=" * 80)
        for key in sorted(all_tag_keys):
            print(f"  - {key}")

        if cluster_tags:
            print(f"\nCluster tags found:")
            for tag in sorted(cluster_tags):
                print(f"  - {tag}")

        if namespace_tags:
            print(f"\nNamespace tags found:")
            for tag in sorted(namespace_tags):
                print(f"  - {tag}")

    except Exception as e:
        print(f"Error fetching CLOUD_APPLICATION entities: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Debug Dynatrace API and discover entity types'
    )
    parser.add_argument(
        '--cluster',
        help='Kubernetes cluster name (optional)'
    )
    parser.add_argument(
        '--namespace',
        help='Kubernetes namespace (optional)'
    )
    parser.add_argument(
        '--test-entity-type',
        help='Test a specific entity type'
    )
    parser.add_argument(
        '--show-all-apps',
        action='store_true',
        help='Show all CLOUD_APPLICATION entities and their tags'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("Dynatrace API Debug Tool")
    print("=" * 80)
    print()

    # Initialize client
    try:
        client = DynatraceClient()
        print(f"Dynatrace URL: {client.base_url}")
        print(f"API Token: {'*' * 20}{client.api_token[-10:]}\n")
    except Exception as e:
        print(f"Error initializing client: {e}")
        return 1

    # Test API connection
    if not test_api_connection(client):
        return 1

    # Show all apps if requested
    if args.show_all_apps:
        show_all_cloud_applications(client)
        return 0

    # List entity types
    entity_types = list_entity_types(client)

    # Test specific entity type if provided
    if args.test_entity_type:
        test_entity_query(client, args.test_entity_type, args.cluster, args.namespace)
    else:
        # Test common Kubernetes entity types
        print("\n" + "=" * 80)
        print("Testing common Kubernetes entity types:")
        print("=" * 80)

        common_types = [
            'CLOUD_APPLICATION',
            'CLOUD_APPLICATION_WORKLOAD',
            'WORKLOAD',
            'CLOUD_APPLICATION_INSTANCE',
            'KUBERNETES_CLUSTER',
            'KUBERNETES_NODE'
        ]

        for entity_type in common_types:
            if entity_type in entity_types:
                test_entity_query(client, entity_type, args.cluster, args.namespace)

    print("\n" + "=" * 80)
    print("Debug complete!")
    print("=" * 80)
    print("\nTIP: Use --show-all-apps to see all CLOUD_APPLICATION entities and their exact tag format")


if __name__ == '__main__':
    exit(main())

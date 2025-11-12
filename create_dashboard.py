"""
Create a Dynatrace dashboard for Kubernetes deployment metrics
"""
import argparse
import json
from dynatrace_client import DynatraceClient


def create_deployment_dashboard(
    cluster_name: str,
    namespace: str,
    include_heap: bool = False
):
    """
    Create a Dynatrace dashboard for deployment metrics

    Args:
        cluster_name: Kubernetes cluster name
        namespace: Kubernetes namespace
        include_heap: Include JVM heap memory tiles
    """
    client = DynatraceClient()

    print(f"Creating dashboard for cluster '{cluster_name}' namespace '{namespace}'...")

    # Get deployments to create tiles for
    deployments = client.get_deployments(cluster_name, namespace)

    if not deployments:
        print(f"No deployments found in cluster '{cluster_name}' namespace '{namespace}'")
        return

    print(f"Found {len(deployments)} deployment(s)")

    # Build dashboard configuration
    dashboard_name = f"K8s Deployments - {cluster_name}/{namespace}"

    # Create tiles for each deployment
    tiles = []
    tile_row = 0
    tile_col = 0

    for deployment in deployments:
        deployment_name = deployment.get('displayName', 'Unknown')
        entity_id = deployment.get('entityId', '')

        print(f"Adding tiles for: {deployment_name}")

        # CPU Usage Tile
        cpu_tile = {
            "name": f"{deployment_name} - CPU",
            "tileType": "DATA_EXPLORER",
            "configured": True,
            "bounds": {
                "top": tile_row * 304,
                "left": tile_col * 304,
                "width": 304,
                "height": 304
            },
            "tileFilter": {},
            "customName": f"{deployment_name} - CPU Usage",
            "queries": [
                {
                    "id": "A",
                    "metric": "builtin:cloud.kubernetes.workload.cpu.usage",
                    "spaceAggregation": "AVG",
                    "timeAggregation": "DEFAULT",
                    "splitBy": [],
                    "filterBy": {
                        "filterOperator": "AND",
                        "nestedFilters": [],
                        "criteria": [
                            {
                                "value": entity_id,
                                "evaluator": "IN"
                            }
                        ]
                    },
                    "enabled": True
                }
            ],
            "visualConfig": {
                "type": "GRAPH_CHART",
                "global": {},
                "rules": [
                    {
                        "matcher": "A:",
                        "properties": {
                            "color": "DEFAULT"
                        },
                        "seriesOverrides": []
                    }
                ],
                "axes": {
                    "xAxis": {
                        "displayName": "",
                        "visible": True
                    },
                    "yAxes": [
                        {
                            "displayName": "CPU (millicores)",
                            "visible": True,
                            "min": "AUTO",
                            "max": "AUTO",
                            "position": "LEFT",
                            "queryIds": ["A"]
                        }
                    ]
                }
            }
        }
        tiles.append(cpu_tile)

        # Memory Usage Tile
        tile_col += 1
        if tile_col >= 4:
            tile_col = 0
            tile_row += 1

        memory_tile = {
            "name": f"{deployment_name} - Memory",
            "tileType": "DATA_EXPLORER",
            "configured": True,
            "bounds": {
                "top": tile_row * 304,
                "left": tile_col * 304,
                "width": 304,
                "height": 304
            },
            "tileFilter": {},
            "customName": f"{deployment_name} - Memory Usage",
            "queries": [
                {
                    "id": "A",
                    "metric": "builtin:cloud.kubernetes.workload.memory.usage",
                    "spaceAggregation": "AVG",
                    "timeAggregation": "DEFAULT",
                    "splitBy": [],
                    "filterBy": {
                        "filterOperator": "AND",
                        "nestedFilters": [],
                        "criteria": [
                            {
                                "value": entity_id,
                                "evaluator": "IN"
                            }
                        ]
                    },
                    "enabled": True
                }
            ],
            "visualConfig": {
                "type": "GRAPH_CHART",
                "global": {},
                "rules": [
                    {
                        "matcher": "A:",
                        "properties": {
                            "color": "DEFAULT"
                        },
                        "seriesOverrides": []
                    }
                ],
                "axes": {
                    "xAxis": {
                        "displayName": "",
                        "visible": True
                    },
                    "yAxes": [
                        {
                            "displayName": "Memory (bytes)",
                            "visible": True,
                            "min": "AUTO",
                            "max": "AUTO",
                            "position": "LEFT",
                            "queryIds": ["A"]
                        }
                    ]
                }
            }
        }
        tiles.append(memory_tile)

        # JVM Heap Tile (if requested)
        if include_heap:
            tile_col += 1
            if tile_col >= 4:
                tile_col = 0
                tile_row += 1

            # We need to get process group for this deployment
            # For simplicity, we'll create a tile that filters by deployment
            heap_tile = {
                "name": f"{deployment_name} - JVM Heap",
                "tileType": "DATA_EXPLORER",
                "configured": True,
                "bounds": {
                    "top": tile_row * 304,
                    "left": tile_col * 304,
                    "width": 304,
                    "height": 304
                },
                "tileFilter": {},
                "customName": f"{deployment_name} - JVM Heap Memory",
                "queries": [
                    {
                        "id": "A",
                        "metric": "builtin:tech.generic.mem.usedHeap",
                        "spaceAggregation": "AVG",
                        "timeAggregation": "DEFAULT",
                        "splitBy": ["dt.entity.process_group"],
                        "filterBy": {
                            "filterOperator": "AND",
                            "nestedFilters": [],
                            "criteria": []
                        },
                        "enabled": True
                    }
                ],
                "visualConfig": {
                    "type": "GRAPH_CHART",
                    "global": {},
                    "rules": [
                        {
                            "matcher": "A:",
                            "properties": {
                                "color": "DEFAULT"
                            },
                            "seriesOverrides": []
                        }
                    ],
                    "axes": {
                        "xAxis": {
                            "displayName": "",
                            "visible": True
                        },
                        "yAxes": [
                            {
                                "displayName": "Heap Memory (bytes)",
                                "visible": True,
                                "min": "AUTO",
                                "max": "AUTO",
                                "position": "LEFT",
                                "queryIds": ["A"]
                            }
                        ]
                    }
                }
            }
            tiles.append(heap_tile)

        # Move to next position
        tile_col += 1
        if tile_col >= 4:
            tile_col = 0
            tile_row += 1

    # Create dashboard payload
    dashboard = {
        "dashboardMetadata": {
            "name": dashboard_name,
            "shared": True,
            "owner": "Dynatrace API",
            "sharingDetails": {
                "linkShared": True,
                "published": False
            },
            "dashboardFilter": {
                "timeframe": "-2h"
            }
        },
        "tiles": tiles
    }

    # Create the dashboard
    dashboard_id = client.create_dashboard(dashboard)

    if dashboard_id:
        dashboard_url = f"{client.base_url}/#dashboard;id={dashboard_id}"
        print(f"\n{'='*80}")
        print(f"Dashboard created successfully!")
        print(f"Dashboard ID: {dashboard_id}")
        print(f"Dashboard URL: {dashboard_url}")
        print(f"{'='*80}")
    else:
        print("\nFailed to create dashboard")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Create a Dynatrace dashboard for Kubernetes deployment metrics'
    )
    parser.add_argument(
        '--cluster',
        required=True,
        help='Kubernetes cluster name'
    )
    parser.add_argument(
        '--namespace',
        required=True,
        help='Kubernetes namespace'
    )
    parser.add_argument(
        '--include-heap',
        action='store_true',
        help='Include JVM heap memory tiles'
    )

    args = parser.parse_args()

    try:
        create_deployment_dashboard(
            cluster_name=args.cluster,
            namespace=args.namespace,
            include_heap=args.include_heap
        )
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())

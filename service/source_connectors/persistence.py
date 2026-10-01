"""Persistence of the code-reviewed source registry into its control tables."""

from __future__ import annotations

import json

import psycopg2.extras

from service.source_connectors.registry import SOURCE_REGISTRY, SourceRegistry


def sync_source_registry(connection, registry: SourceRegistry = SOURCE_REGISTRY) -> None:
    """Idempotently mirror reviewed connector contracts to PostgreSQL."""
    sources = registry.list_sources()
    endpoints = registry.list_endpoints()
    with connection.cursor() as cursor:
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO sys_data_source (
                source_id, display_name, source_kind, acquisition_modes,
                credential_ref, base_url, timezone, license_policy,
                configuration, enabled
            ) VALUES %s
            ON CONFLICT (source_id) DO UPDATE SET
                display_name=EXCLUDED.display_name,
                source_kind=EXCLUDED.source_kind,
                acquisition_modes=EXCLUDED.acquisition_modes,
                credential_ref=EXCLUDED.credential_ref,
                base_url=EXCLUDED.base_url,
                timezone=EXCLUDED.timezone,
                license_policy=EXCLUDED.license_policy,
                configuration=EXCLUDED.configuration,
                enabled=TRUE,
                updated_at=NOW()
            """,
            [
                (
                    source.source_id,
                    source.display_name,
                    source.kind.value,
                    [mode.value for mode in source.acquisition_modes],
                    source.credential_ref,
                    source.base_url,
                    source.timezone,
                    psycopg2.extras.Json(dict(source.license_policy)),
                    psycopg2.extras.Json(dict(source.configuration)),
                    True,
                )
                for source in sources
            ],
        )
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO sys_source_endpoint (
                source_id, endpoint_key, title, acquisition_mode,
                resource_class, cadence, parser_name, parser_version,
                cache_ttl_seconds, request_contract,
                completeness_policy, enabled
            ) VALUES %s
            ON CONFLICT (source_id, endpoint_key) DO UPDATE SET
                title=EXCLUDED.title,
                acquisition_mode=EXCLUDED.acquisition_mode,
                resource_class=EXCLUDED.resource_class,
                cadence=EXCLUDED.cadence,
                parser_name=EXCLUDED.parser_name,
                parser_version=EXCLUDED.parser_version,
                cache_ttl_seconds=EXCLUDED.cache_ttl_seconds,
                request_contract=EXCLUDED.request_contract,
                completeness_policy=EXCLUDED.completeness_policy,
                enabled=TRUE,
                updated_at=NOW()
            """,
            [
                (
                    endpoint.source_id,
                    endpoint.endpoint_key,
                    endpoint.title,
                    endpoint.acquisition_mode.value,
                    endpoint.resource_class,
                    endpoint.cadence,
                    endpoint.parser_name,
                    endpoint.parser_version,
                    endpoint.cache_ttl_seconds,
                    psycopg2.extras.Json(
                        dict(endpoint.request_contract),
                        dumps=lambda value: json.dumps(value, ensure_ascii=False),
                    ),
                    psycopg2.extras.Json(
                        dict(endpoint.completeness_policy),
                        dumps=lambda value: json.dumps(value, ensure_ascii=False),
                    ),
                    True,
                )
                for endpoint in endpoints
            ],
            page_size=500,
        )
        cursor.execute(
            """
            UPDATE sys_source_endpoint endpoint
               SET enabled=FALSE, updated_at=NOW()
             WHERE NOT EXISTS (
                 SELECT 1
                   FROM unnest(%s::text[], %s::text[]) AS active(source_id, endpoint_key)
                  WHERE active.source_id=endpoint.source_id
                    AND active.endpoint_key=endpoint.endpoint_key
             )
            """,
            (
                [endpoint.source_id for endpoint in endpoints],
                [endpoint.endpoint_key for endpoint in endpoints],
            ),
        )

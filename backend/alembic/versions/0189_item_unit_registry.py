"""INV-02: item unit registry, exact fixed rules and observed batch ratios.

Legacy primary/secondary columns remain for compatibility. No historical
document or ledger quantity is recalculated using today's conversion factor.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from app.migration_utils import rls_disabled
from app.tenancy import rls_statements

revision = "0189"
down_revision = "0188"
branch_labels = None
depends_on = None
TABLES = ("item_units", "item_unit_conversions", "batch_unit_conversions")
PARENTS = ("items", "units_of_measure", "stock_batches")
QUANTITY_COLUMNS = (('batch_substitutions', 'qty'), ('bom_lines', 'qty'), ('boms', 'yield_qty'), ('enterprise_market_catalog', 'available_qty'), ('enterprise_market_catalog', 'staged_available_qty'), ('inventory_valuation_adjustments', 'qty'), ('item_warehouses', 'max_stock'), ('item_warehouses', 'min_stock'), ('items', 'max_stock'), ('items', 'min_stock'), ('items', 'reorder_point'), ('marketplace_catalog_allocations', 'qty'), ('marketplace_listing_components', 'qty'), ('marketplace_listings', 'bonus_qty'), ('marketplace_listings', 'bonus_threshold_qty'), ('marketplace_listings', 'max_order_qty'), ('marketplace_listings', 'min_order_qty'), ('marketplace_order_lines', 'qty'), ('marketplace_return_lines', 'qty'), ('product_bundle_lines', 'qty'), ('production_order_lines', 'qty'), ('production_orders', 'qty_produced'), ('production_plans', 'qty_planned'), ('production_plans', 'qty_produced'), ('purchase_invoice_lines', 'bonus_qty'), ('purchase_invoice_lines', 'qty'), ('purchase_return_lines', 'qty'), ('sales_invoice_lines', 'qty'), ('sales_quotation_lines', 'qty'), ('sales_return_lines', 'qty'), ('stock_adjustments', 'qty_diff'), ('stock_batches', 'qty'), ('stock_batches', 'received_qty'), ('stock_count_lines', 'counted_qty'), ('stock_count_lines', 'system_qty'), ('stock_ledger', 'qty'), ('stock_reservations', 'qty'), ('stock_transfer_lines', 'qty'), ('storefront_order_lines', 'qty'), ('warehouse_issue_lines', 'qty'), ('warehouse_issue_lines', 'secondary_qty'), ('warehouse_issue_return_lines', 'qty'), ('warehouse_issue_return_lines', 'secondary_qty'), ('warehouse_receipt_lines', 'qty'))
QUANTITY_TABLES = tuple(sorted({table for table, column in QUANTITY_COLUMNS}))
SNAPSHOT_TABLES = (('boms', 'finished_item_id', 'yield_qty', False, False), ('production_plans', 'finished_item_id', 'qty_planned', False, False), ('production_orders', 'finished_item_id', 'qty_produced', False, False), ('bom_lines', 'component_item_id', 'qty', False, False), ('production_order_lines', 'component_item_id', 'qty', False, False), ('purchase_invoice_lines', 'item_id', 'qty', True, True), ('purchase_return_lines', 'item_id', 'qty', True, False), ('sales_invoice_lines', 'item_id', 'qty', True, True), ('sales_quotation_lines', 'item_id', 'qty', True, True), ('sales_return_lines', 'item_id', 'qty', True, False), ('stock_adjustments', 'item_id', 'qty_diff', False, False), ('stock_ledger', 'item_id', 'qty', False, False), ('stock_transfer_lines', 'item_id', 'qty', False, False), ('warehouse_issue_lines', 'item_id', 'qty', False, True), ('warehouse_issue_return_lines', 'item_id', 'qty', False, True), ('warehouse_receipt_lines', 'item_id', 'qty', False, True))
DDL = (
    "CREATE TABLE item_units (\n\titem_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tpurchase_allowed BOOLEAN DEFAULT 'true' NOT NULL, \n\tsale_allowed BOOLEAN DEFAULT 'true' NOT NULL, \n\tinventory_allowed BOOLEAN DEFAULT 'true' NOT NULL, \n\tproduction_allowed BOOLEAN DEFAULT 'true' NOT NULL, \n\tdecimal_allowed BOOLEAN DEFAULT 'true' NOT NULL, \n\tis_active BOOLEAN DEFAULT 'true' NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_item_units_identity UNIQUE (tenant_id, item_id, unit_id), \n\tCONSTRAINT fk_item_unit_item FOREIGN KEY(tenant_id, item_id) REFERENCES items (tenant_id, id) ON DELETE CASCADE, \n\tCONSTRAINT fk_item_unit_unit FOREIGN KEY(tenant_id, unit_id) REFERENCES units_of_measure (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE\n)",
    'CREATE INDEX ix_item_units_tenant_id ON item_units (tenant_id)',
    "CREATE TABLE item_unit_conversions (\n\titem_id UUID NOT NULL, \n\tfrom_unit_id UUID NOT NULL, \n\tto_unit_id UUID NOT NULL, \n\tmode VARCHAR(12) DEFAULT 'fixed' NOT NULL, \n\tfactor NUMERIC(30, 12), \n\tversion INTEGER DEFAULT '1' NOT NULL, \n\tis_active BOOLEAN DEFAULT 'true' NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_item_conversion_pair UNIQUE (tenant_id, item_id, from_unit_id, to_unit_id), \n\tCONSTRAINT uq_item_conversion_identity UNIQUE (tenant_id, item_id, id), \n\tCONSTRAINT fk_item_conversion_from FOREIGN KEY(tenant_id, item_id, from_unit_id) REFERENCES item_units (tenant_id, item_id, unit_id) ON DELETE CASCADE, \n\tCONSTRAINT fk_item_conversion_to FOREIGN KEY(tenant_id, item_id, to_unit_id) REFERENCES item_units (tenant_id, item_id, unit_id) ON DELETE CASCADE, \n\tCONSTRAINT ck_item_conversion_not_self CHECK (from_unit_id <> to_unit_id), \n\tCONSTRAINT ck_item_conversion_factor CHECK ((mode = 'fixed' AND factor > 0 AND factor IS NOT NULL) OR (mode = 'variable' AND factor IS NULL)), \n\tCONSTRAINT ck_item_conversion_version CHECK (version > 0), \n\tCONSTRAINT ck_item_conversion_finite CHECK (factor IS NULL OR factor::text NOT IN ('NaN', 'Infinity', '-Infinity')), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE\n)",
    'CREATE INDEX ix_item_unit_conversions_tenant_id ON item_unit_conversions (tenant_id)',
    "CREATE TABLE batch_unit_conversions (\n\titem_id UUID NOT NULL, \n\tbatch_id UUID NOT NULL, \n\trule_id UUID NOT NULL, \n\tfrom_qty NUMERIC(24, 8) NOT NULL, \n\tto_qty NUMERIC(24, 8) NOT NULL, \n\tapproved_by_id UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_batch_conversion_rule UNIQUE (tenant_id, batch_id, rule_id), \n\tCONSTRAINT fk_batch_conversion_rule FOREIGN KEY(tenant_id, item_id, rule_id) REFERENCES item_unit_conversions (tenant_id, item_id, id), \n\tCONSTRAINT fk_batch_conversion_batch FOREIGN KEY(tenant_id, item_id, batch_id) REFERENCES stock_batches (tenant_id, item_id, id), \n\tCONSTRAINT ck_batch_conversion_observations CHECK (from_qty > 0 AND to_qty > 0), \n\tCONSTRAINT ck_batch_conversion_finite CHECK (from_qty::text NOT IN ('NaN', 'Infinity', '-Infinity') AND to_qty::text NOT IN ('NaN', 'Infinity', '-Infinity')), \n\tFOREIGN KEY(approved_by_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE\n)",
    'CREATE INDEX ix_batch_unit_conversions_tenant_id ON batch_unit_conversions (tenant_id)',
)


def upgrade():
    conn = op.get_bind()
    with rls_disabled(conn, tuple(dict.fromkeys((*PARENTS, *QUANTITY_TABLES, *(row[0] for row in SNAPSHOT_TABLES))))):
        invalid = conn.execute(sa.text("""
            SELECT i.id FROM items i
            LEFT JOIN units_of_measure p ON p.id=i.primary_unit_id AND p.tenant_id=i.tenant_id
            LEFT JOIN units_of_measure s ON s.id=i.secondary_unit_id AND s.tenant_id=i.tenant_id
            WHERE (i.primary_unit_id IS NULL AND trim(coalesce(i.unit,''))='')
               OR (i.primary_unit_id IS NOT NULL AND p.id IS NULL)
               OR (i.secondary_unit_id IS NOT NULL AND s.id IS NULL)
               OR i.primary_unit_id=i.secondary_unit_id
               OR (i.primary_unit_id IS NULL AND s.name=trim(i.unit))
               OR (i.secondary_unit_id IS NOT NULL AND
                   (i.conversion_mode NOT IN ('fixed','variable') OR
                    (i.conversion_mode='fixed' AND (i.conversion_factor IS NULL OR i.conversion_factor<=0 OR
                     i.conversion_factor::text IN ('NaN','Infinity','-Infinity')))))
            LIMIT 20
        """)).scalars().all()
        if invalid:
            raise RuntimeError(f"INV-02 invalid legacy units; repair item IDs before migration: {invalid}")
        conn.execute(sa.text("""
            INSERT INTO units_of_measure (id,tenant_id,name,name2,is_active,created_at,updated_at)
            SELECT gen_random_uuid(), x.tenant_id, x.name, '', true, now(), now()
            FROM (SELECT DISTINCT tenant_id,trim(unit) AS name FROM items WHERE primary_unit_id IS NULL) x
            ON CONFLICT (tenant_id,name) DO NOTHING
        """))
        conn.execute(sa.text("""
            UPDATE items i SET primary_unit_id=u.id
            FROM units_of_measure u
            WHERE i.primary_unit_id IS NULL AND u.tenant_id=i.tenant_id AND u.name=trim(i.unit)
        """))
        op.create_unique_constraint("uq_items_tenant_id", "items", ["tenant_id", "id"])
        op.create_unique_constraint("uq_units_tenant_id", "units_of_measure", ["tenant_id", "id"])
        op.create_unique_constraint("uq_stock_batch_item_identity", "stock_batches", ["tenant_id", "item_id", "id"])
        for table, column in QUANTITY_COLUMNS:
            op.alter_column(table, column, type_=sa.Numeric(24, 8), existing_type=sa.Numeric(18, 3))
        op.alter_column("items", "conversion_factor", type_=sa.Numeric(30, 12), existing_type=sa.Numeric(18, 6))
        for table, item_column, qty_column, commercial, has_name in SNAPSHOT_TABLES:
            op.add_column(table, sa.Column("entered_qty", sa.Numeric(24, 8), nullable=True))
            op.add_column(table, sa.Column("entered_unit_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.add_column(table, sa.Column("base_unit_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.add_column(table, sa.Column("unit_conversion_snapshot", postgresql.JSONB(), nullable=True))
            for field in ("entered_unit_id", "base_unit_id"):
                op.create_foreign_key(f"fk_{table}_{field}", table, "units_of_measure", ["tenant_id", field], ["tenant_id", "id"])
            if commercial:
                op.add_column(table, sa.Column("base_qty", sa.Numeric(24, 8), nullable=True))
            historical_name = "coalesce(nullif(d.unit_snapshot,''),i.unit)" if has_name else "i.unit"
            base_assignment = f', base_qty=d."{qty_column}"' if commercial else ''
            conn.execute(sa.text(f"""
                UPDATE "{table}" d SET entered_qty=d."{qty_column}",
                  entered_unit_id=(SELECT u.id FROM units_of_measure u WHERE u.tenant_id=i.tenant_id AND u.name={historical_name}),
                  base_unit_id=(SELECT u.id FROM units_of_measure u WHERE u.tenant_id=i.tenant_id AND u.name={historical_name}),
                  unit_conversion_snapshot=jsonb_build_object(
                    'schema_version',1,'source','legacy_base','original_input_known',false,
                    'source_qty',d."{qty_column}"::text,'target_qty',d."{qty_column}"::text,
                    'source_unit_name',{historical_name},'target_unit_name',{historical_name},
                    'numerator','1','denominator','1','path','[]'::jsonb,'scale',8,'rounding','ROUND_HALF_UP')
                  {base_assignment}
                FROM items i WHERE i.id=d."{item_column}" AND i.tenant_id=d.tenant_id
            """))
        for statement in DDL:
            conn.execute(sa.text(statement))
        conn.execute(sa.text("""
            INSERT INTO item_units (id,tenant_id,item_id,unit_id)
            SELECT gen_random_uuid(),tenant_id,id,primary_unit_id FROM items
            UNION ALL
            SELECT gen_random_uuid(),tenant_id,id,secondary_unit_id FROM items WHERE secondary_unit_id IS NOT NULL
        """))
        conn.execute(sa.text("""
            INSERT INTO item_unit_conversions (id,tenant_id,item_id,from_unit_id,to_unit_id,mode,factor)
            SELECT gen_random_uuid(),tenant_id,id,secondary_unit_id,primary_unit_id,conversion_mode,
                   CASE WHEN conversion_mode='fixed' THEN conversion_factor ELSE NULL END
            FROM items WHERE secondary_unit_id IS NOT NULL
        """))
    op.add_column("production_plans", sa.Column("recipe_snapshot", postgresql.JSONB(), nullable=True))
    op.alter_column("items", "primary_unit_id", nullable=False)
    op.create_foreign_key("fk_items_base_membership", "items", "item_units",
        ["tenant_id", "id", "primary_unit_id"], ["tenant_id", "item_id", "unit_id"],
        deferrable=True, initially="DEFERRED")
    for statement in rls_statements(TABLES):
        conn.execute(sa.text(statement))


def downgrade():
    conn = op.get_bind()
    with rls_disabled(conn, tuple(dict.fromkeys((*TABLES, *PARENTS, *QUANTITY_TABLES, *(row[0] for row in SNAPSHOT_TABLES))))):
        for table, column in QUANTITY_COLUMNS:
            # Identifiers are a frozen migration-owned list, never user input.
            changed = conn.execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM "{table}" WHERE "{column}" <> round("{column}",3) OR abs("{column}")>=1000000000000000)')).scalar_one()
            if changed:
                raise RuntimeError(f"INV-02 downgrade loses quantity precision: {table}.{column}; restore a verified backup")
        for table, item_column, qty_column, commercial, has_name in SNAPSHOT_TABLES:
            used = conn.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM \"{table}\" WHERE unit_conversion_snapshot IS NOT NULL AND unit_conversion_snapshot->>'source' IS DISTINCT FROM 'legacy_base')")).scalar_one()
            if used:
                raise RuntimeError(f"INV-02 downgrade discards historical conversion snapshots: {table}; restore a verified backup")
        incompatible = conn.execute(sa.text("""
            SELECT EXISTS(SELECT 1 FROM items WHERE conversion_factor <> round(conversion_factor,6) OR abs(conversion_factor)>=1000000000000)
             OR EXISTS(SELECT 1 FROM batch_unit_conversions)
             OR EXISTS(SELECT 1 FROM item_units u JOIN items i ON i.id=u.item_id AND i.tenant_id=u.tenant_id
                       WHERE u.unit_id NOT IN (i.primary_unit_id,coalesce(i.secondary_unit_id,i.primary_unit_id))
                          OR NOT u.purchase_allowed OR NOT u.sale_allowed OR NOT u.inventory_allowed
                          OR NOT u.production_allowed OR NOT u.decimal_allowed OR NOT u.is_active)
             OR EXISTS(SELECT 1 FROM item_unit_conversions c JOIN items i ON i.id=c.item_id AND i.tenant_id=c.tenant_id
                       WHERE c.from_unit_id IS DISTINCT FROM i.secondary_unit_id OR c.to_unit_id<>i.primary_unit_id
                          OR c.mode<>i.conversion_mode OR NOT c.is_active
                          OR (c.mode='fixed' AND c.factor IS DISTINCT FROM i.conversion_factor))
        """)).scalar_one()
        if incompatible:
            raise RuntimeError("INV-02 downgrade would discard multi-unit data; restore a verified pre-upgrade backup instead")
    op.drop_column("production_plans", "recipe_snapshot")
    op.drop_constraint("fk_items_base_membership", "items", type_="foreignkey")
    op.alter_column("items", "primary_unit_id", nullable=True)
    for table, item_column, qty_column, commercial, has_name in SNAPSHOT_TABLES:
        for column in ("unit_conversion_snapshot", "base_unit_id", "entered_unit_id", "entered_qty"):
            op.drop_column(table, column)
        if commercial:
            op.drop_column(table, "base_qty")
    for table, column in QUANTITY_COLUMNS:
        op.alter_column(table, column, type_=sa.Numeric(18, 3), existing_type=sa.Numeric(24, 8))
    op.alter_column("items", "conversion_factor", type_=sa.Numeric(18, 6), existing_type=sa.Numeric(30, 12))
    for table in reversed(TABLES):
        op.drop_table(table)
    op.drop_constraint("uq_stock_batch_item_identity", "stock_batches", type_="unique")
    op.drop_constraint("uq_units_tenant_id", "units_of_measure", type_="unique")
    op.drop_constraint("uq_items_tenant_id", "items", type_="unique")

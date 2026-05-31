import indicatorSchema from "../../../../datasets/schemas/indicator.schema.json";

interface IndicatorSchemaPolicy {
  $id: string;
  "x-version": string;
}

const policy = indicatorSchema as IndicatorSchemaPolicy;

export const CURRENT_INDICATOR_SCHEMA_ID = policy.$id;
export const CURRENT_INDICATOR_SCHEMA_VERSION = policy["x-version"];
import json
import boto3
import os
from datetime import datetime
from typing import Dict, List, Any
import uuid

s3_client = boto3.client('s3')
glue_client = boto3.client('glue')
athena_client = boto3.client('athena')
dynamodb = boto3.resource('dynamodb')
dq_table = dynamodb.Table(os.environ['DQ_METRICS_TABLE'])
sns_client = boto3.client('sns')

# Data quality rules
DQ_RULES = {
    'dim_game': {
        'completeness': {
            'required_fields': ['game_id', 'name', 'year_published'],
            'threshold': 0.95
        },
        'validity': {
            'year_published': {
                'min': 1900,
                'max': datetime.now().year +5
            },
            'min_players': {
                    'min': 1,
                    'max': 100
                },
            'max_players': {
                    'min': 1,
                    'max': 100
            },
            'average_rating': {
                    'min': 0,
                    'max': 10
            }
        },  
        'consistency': {
            'players': 'min_players <= max_players',
            'playtime': 'min_playtime <= max_playtime'
        },
        'uniqueness': {
            'fields': ['game_id']
        }
    },
    'br_game_category': {
        'referential_integrity': {
            'game_id': 'dim_game.game_id',
            'category_id': 'dim_category.category_id'
        }
    },
    'br_game_mechanic': {
        'referential_integrity': {
            'game_id': 'dim_game.game_id',
            'mechanic_id': 'dim_mechanic.mechanic_id'
        }
    }
}

def lambda_handler(event, context):
    """
    Run data quality checks on transformed data.
    """

    database_name = os.environ['GLUE_DATABASE']
    table_name = event.get('table_name', 'dim_game')
    s3_output_location = os.environ['ATHENA_OUTPUT_LOCATION']

    check_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    results = {
        'check_id': check_id,
        'timestamp': timestamp,
        'table_name': table_name,
        'checks': {}
    }

    if table_name not in DQ_RULES:
        return {
            'statusCode': 400,
            'body': json.dumps({"error": f"No data quality rules defined for table {table_name}"})
        }
    
    rules = DQ_RULES[table_name]

    # Run completeness checks
    if 'completeness' in rules:
        results['checks']['completeness'] = check_completeness(
            database_name, table_name, rules['completeness'], s3_output_location
        )
    
    # Run validity checks
    if 'validity' in rules:
        results['checks']['validity'] = check_validity(
            database_name, table_name, rules['validity'], s3_output_location
        )
    
    # Run consistency checks
    if 'consistency' in rules:
        results['checks']['consistency'] = check_consistency(
            database_name, table_name, rules['consistency'], s3_output_location
        )
    
    # Run uniqueness checks
    if 'uniqueness' in rules:
        results['checks']['uniqueness'] = check_uniqueness(
            database_name, table_name, rules['uniqueness'], s3_output_location
        )
    
    # Run referential integrity checks
    if 'referential_integrity' in rules:
        results['checks']['referential_integrity'] = check_referential_integrity(
            database_name, table_name, rules['referential_integrity'], s3_output_location
        )
    
    # Calculate overall status
    all_passed = all(
        check.get('passed',False)
        for check_type in results['checks'].values()
        for check in (check_type if isinstance(check_type, list) else [check_type])
    )

    results['overall_status'] = 'PASSED' if all_passed else 'FAILED'

    # Store results in DynamoDB
    store_dq_results(results)

    # Send alert if failed
    if not all_passed:
        send_dq_alert(results)

    return {
        'statusCode': 200,
        'body': json.dumps(results, default=str)
    }

def execute_athena_query(query: str, database: str, output_location: str) -> List[Dict]:
    """Execute Athena query and return results."""
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location}
    )
    query_execution_id = response['QueryExecutionId']

    # Wait for the query to complete
    import time
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        time.sleep(1)

    if status != 'SUCCEEDED':
        raise Exception(f"Athena query failed with status: {status}")

    # Fetch results
    results = athena_client.get_query_results(QueryExecutionId=query_execution_id)

    # Parse results
    rows = results['ResultSet']['Rows']
    if len(rows) <= 1:
        return []
    
    headers = [col['VarCharValue'] for col in rows[0]['Data']]
    data = []

    for row in rows[1:]:
        row_data = {}
        for i, col in enumerate(row['Data']):
            row_data[headers[i]] = col.get('VarCharValue', None)
        data.append(row_data)
    
    return data

def check_completeness(database: str, table: str, rules: Dict, output_location: str) -> Dict:
    """Check if required fields are populated."""

    required_fields = rules['required_fields']
    threshold = rules['threshold']

    # Build query to count nulls
    null_checks = [
        f"SUM(CASE WHEN {field} IS NULL THEN 1 ELSE 0 END) AS {field}_nulls"
        for field in required_fields
    ]

    query = f"""
    SELECT
        COUNT(*) AS total_records,
        {', '.join(null_checks)}
    FROM {table}
    """

    results = execute_athena_query(query, database, output_location)

    if not results:
        return {'passed': False, 'error': 'No results returned'}
    
    total = int(results[0]['total_records'])
    field_results = {}

    for field in required_fields:
        nulls = int(results[0][f"{field}_nulls"])
        completeness = (total - nulls) / total if total > 0 else 0
        passed = completeness >= threshold

        field_results[field] = {
            'completeness': completeness,
            'threshold': threshold,
            'passed': passed,
            'null_count': nulls,
            'total_count': total
        }

    overall_passed = all(r['passed'] for r in field_results.values())

    return {
        'passed': overall_passed,
        'results': field_results
    }

def check_validity(database: str, table: str, rules: Dict, output_location: str) -> Dict:
    """Check if field values fall within valid ranges."""

    field_results = {}

    for field, constraints in rules.items():
        min_val = constraints['min']
        max_val = constraints['max']

        conditions = []
        if min_val is not None:
            conditions.append(f"{field} < {min_val}")
        if max_val is not None: 
            conditions.append(f"{field} > {max_val}")

        if not conditions:
            continue

        query = f"""
        SELECT
            COUNT(*) AS total_records,
            SUM(CASE WHEN {' OR '.join(conditions)} THEN 1 ELSE 0 END) AS invalid_records
        FROM {table}
        WHERE {field} IS NOT NULL
        """

        results = execute_athena_query(query, database, output_location)

        if results:
            total = int(results[0]['total_records'])
            invalids = int(results[0]['invalid_records'])
            validity_rate = (total - invalids) / total if total > 0 else 1.0

            field_results[field] = {
                'validity_rate': validity_rate,
                'invalid_count': invalids,
                'total_count': total,
                'passed': invalids == 0,
                'constraints': constraints
            }

    overall_passed = all(r['passed'] for r in field_results.values())

    return {
        'passed': overall_passed,
        'results': field_results
    }

def check_consistency(database: str, table: str, rules: Dict, output_location: str) -> Dict:
    """Check cross-field consistency."""

    rule_results = {}

    for rule_name, condition in rules.items():
        query = f"""
        SELECT
            COUNT(*) AS total_records,
            SUM(CASE WHEN NOT ({condition}) THEN 1 ELSE 0 END) AS inconsistent_records
        FROM {table}
        """

        results = execute_athena_query(query, database, output_location)

        if results:
            total = int(results[0]['total_records'])
            inconsistent = int(results[0]['inconsistent_records'])

            rule_results[rule_name] = {
                'condition': condition,
                'inconsistent_count': inconsistent,
                'total_count': total,
                'passed': inconsistent == 0,
            }

    overall_passed = all(r['passed'] for r in rule_results.values())

    return {
        'passed': overall_passed,
        'rules': rule_results
    }

def check_uniqueness(database: str, table: str, rules: Dict, output_location: str) -> Dict:
    """Check for duplicate records."""

    unique_fields = rules['fields']
    fields_str = ', '.join(unique_fields)

    query = f"""
    SELECT
        {fields_str},
        COUNT(*) AS duplicate_count
    FROM {table}
    GROUP BY {fields_str}
    HAVING COUNT(*) > 1
    """

    results = execute_athena_query(query, database, output_location)

    return {
        'passed': len(results) == 0,
        'duplicate_count': len(results),
        'fields': unique_fields,
        'duplicates': results[:10]  # Return first 10 duplicates
    }

def check_referential_integrity(database: str, table: str, rules: Dict, output_location: str) -> Dict:
    """Check foreign key relationships."""

    integrity_results = {}

    for field, reference in rules.items():
        ref_table, ref_field = reference.split('.')

        query = f"""
        SELECT
            COUNT(*) AS orphan_count
        FROM {table} t
        LEFT JOIN {ref_table} r ON t.{field} = r.{ref_field}
        WHERE r.{ref_field} IS NULL AND t.{field} IS NOT NULL
        """

        results = execute_athena_query(query, database, output_location)

        if results:
            orphan_count = int(results[0]['orphan_count'])

            integrity_results[field] = {
                'reference': reference,
                'orphan_count': orphan_count,
                'passed': orphan_count == 0
            }

    overall_passed = all(r['passed'] for r in integrity_results.values())

    return {
        'passed': overall_passed,
        'results': integrity_results
    }

def store_dq_results(results: Dict):
    """Store data quality results in DynamoDB."""
    dq_table.put_item(Item=results)

def send_dq_alert(results: Dict):
    """Send SNS alert if data quality checks fail."""

    topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not topic_arn:
        return
    
    failed_checks = []
    for check_type, check_results in results['checks'].items():
        if isinstance(check_results, dict) and not check_results.get('passed'):
            failed_checks.append({check_type: check_results})

    message = f"""
    Data Quality Check FAILED
    Table: {results['table_name']} 
    Timestamp: {results['timestamp']}
    Check ID: {results['check_id']}
    
    Failed Checks: {', '.join(failed_checks)} 
    
    Please review the detailed results in the DynamoDB table.
    """
    sns_client.publish(
        TopicArn=topic_arn,
        Subject=f"Data Quality Alert: {results['table_name']} FAILED",
        Message=message
    )
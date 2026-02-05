# Pipeline Validation Tests

## 1. Data Quality Metrics Validation
Check that DQ metrics were stored in DynamoDB:

```powershell
# Get the most recent data quality check
aws dynamodb scan --table-name boardgames_sommelier-dq-metrics-dev --region ap-southeast-2 --max-items 1 | ConvertFrom-Json | Select-Object -ExpandProperty Items
```

**Expected**: Should return check results with completeness, validity, consistency, and uniqueness metrics.

---

## 2. Verify Data in Each Layer

### Bronze Layer (Raw BGG Data)
```powershell
# Check bronze layer has data
aws s3 ls s3://boardgames-sommelier-bronze-dev-021406833830/bgg/ --recursive --region ap-southeast-2 | Select-Object -First 10
```

### Silver Layer (Cleaned Data)
```powershell
# Check dim_game table
aws s3 ls s3://boardgames-sommelier-silver-dev-021406833830/bgg/dim_game/ --recursive --region ap-southeast-2 | Select-Object -First 10
```

### Gold Layer (Bridge Tables)
```powershell
# Check bridge tables
aws s3 ls s3://boardgames-sommelier-gold-dev-021406833830/bgg/ --recursive --region ap-southeast-2 | Select-Object -First 10
```

**Expected**: Each layer should have Parquet files with recent timestamps.

---

## 3. Query Athena to Validate Data

### Check Game Count
```powershell
# Start Athena query
$queryId = (aws athena start-query-execution --query-string "SELECT COUNT(*) as game_count FROM dim_game" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId

# Wait a few seconds, then get results
Start-Sleep -Seconds 5
aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2 | ConvertFrom-Json | Select-Object -ExpandProperty ResultSet
```

### Sample Game Data
```powershell
# Query top games by rating
$queryId = (aws athena start-query-execution --query-string "SELECT primary_name, avg_rating_bgg, num_votes_bgg FROM dim_game WHERE avg_rating_bgg IS NOT NULL ORDER BY avg_rating_bgg DESC LIMIT 10" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId

Start-Sleep -Seconds 5
aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2 | ConvertFrom-Json | Select-Object -ExpandProperty ResultSet
```

**Expected**: Should return actual game data with names, ratings, and vote counts.

---

## 4. Verify dbt Models in Athena

Check that dbt models were created in the analytics_analytics schema:

```powershell
# List tables in analytics_analytics schema
$queryId = (aws athena start-query-execution --query-string "SHOW TABLES IN analytics_analytics" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId
Start-Sleep -Seconds 5
aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2
```

### Query dbt staging model
```powershell
$queryId = (aws athena start-query-execution --query-string "SELECT COUNT(*) FROM analytics_analytics.stg_games" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId

Start-Sleep -Seconds 5
aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2
```

**Expected**: Should see `stg_games` and `dim_game_features` in analytics_analytics.

---

## 5. Validate Glue Crawlers

Check that both crawlers ran successfully:

```powershell
# Check silver crawler
aws glue get-crawler --name boardgames_sommelier_silver_dimensions_crawler --region ap-southeast-2 | ConvertFrom-Json | Select-Object -ExpandProperty Crawler | Select-Object Name, State, LastCrawl

# Check gold crawler
aws glue get-crawler --name boardgames_sommelier_gold_facts_crawler --region ap-southeast-2 | ConvertFrom-Json | Select-Object -ExpandProperty Crawler | Select-Object Name, State, LastCrawl
```

**Expected**: Both should show State = "READY" and LastCrawl with recent timestamp.

---

## 6. Check Bridge Tables

Verify referential integrity of bridge tables:

```powershell
# Check game-category relationships
$queryId = (aws athena start-query-execution --query-string "SELECT g.primary_name, c.category_name FROM br_game_category bgc JOIN dim_game g ON bgc.game_id = g.game_id JOIN dim_category c ON bgc.category_id = c.category_id LIMIT 10" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId

Start-Sleep -Seconds 5
aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2
```

**Expected**: Should return game names with their associated categories.

---

## 7. Verify Airflow DAG Execution History

Check DAG run history in Airflow UI:
- Navigate to: http://3.104.220.103:8080
- Click on the `bgg_etl_pipeline` DAG
- Check "Runs" tab - should see successful run with all 12 tasks completed

**Expected**: All 12 tasks green:
1. game_id_discovery
2. wait_for_game_id_file
3. get_latest_game_id_file
4. extract_bgg_data
5. wait_for_bronze_file
6. wait_for_silver_file
7. apply_mappings
8. wait_for_gold_file
9. dbt_run
10. crawl_silver_layer
11. crawl_gold_layer
12. data_quality

---

## 8. Data Quality Checks Verification

Verify specific DQ checks passed:

```powershell
# Get latest DQ results with details
aws dynamodb scan --table-name boardgames_sommelier-dq-metrics-dev --region ap-southeast-2 | ConvertFrom-Json | Select-Object -ExpandProperty Items | Select-Object -First 1 | ConvertTo-Json -Depth 10
```

**Look for**:
- `completeness`: Check for `game_id` and `primary_name` fields
- `validity`: Check ranges for `min_players`, `max_players`, `avg_rating_bgg`
- `consistency`: Check `min_players <= max_players` and `min_time <= max_time`
- `uniqueness`: Check `game_id` is unique

---

## 9. S3 Event Triggers Verification

Check that S3 event triggers worked:

```powershell
# Check clean_bgg_data Lambda invocations (triggered by bronze)
aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Invocations --dimensions Name=FunctionName,Value=boardgames_sommelier_clean_bgg_data --start-time (Get-Date).AddHours(-2).ToString("yyyy-MM-ddTHH:mm:ss") --end-time (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss") --period 3600 --statistics Sum --region ap-southeast-2

# Check transform_bgg_data Lambda invocations (triggered by silver)
aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Invocations --dimensions Name=FunctionName,Value=boardgames_sommelier_transform_bgg_data --start-time (Get-Date).AddHours(-2).ToString("yyyy-MM-ddTHH:mm:ss") --end-time (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss") --period 3600 --statistics Sum --region ap-southeast-2
```

**Expected**: Both should show at least 1 invocation.

---

## 10. End-to-End Data Lineage Test

Verify a single game made it through the entire pipeline:

```powershell
# Pick a specific game and trace it through layers
$queryId = (aws athena start-query-execution --query-string "SELECT primary_name, year, min_players, max_players, avg_rating_bgg FROM dim_game WHERE primary_name LIKE '%Catan%' LIMIT 5" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId

Start-Sleep -Seconds 5
aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2 | ConvertFrom-Json | Select-Object -ExpandProperty ResultSet
```

**Expected**: Should find popular games like "Catan" with complete attributes.

---

## Quick Validation Script

Run all critical checks at once:

```powershell
Write-Host "`n=== Pipeline Validation ===" -ForegroundColor Cyan

# 1. Check DQ metrics exist
Write-Host "`n1. Data Quality Metrics:" -ForegroundColor Yellow
$dqCount = (aws dynamodb scan --table-name boardgames_sommelier-dq-metrics-dev --region ap-southeast-2 --select COUNT | ConvertFrom-Json).Count
Write-Host "   DQ Metrics Count: $dqCount" -ForegroundColor $(if($dqCount -gt 0){"Green"}else{"Red"})

# 2. Check S3 layers have data
Write-Host "`n2. S3 Data Layers:" -ForegroundColor Yellow
$bronzeCount = (aws s3 ls s3://boardgames-sommelier-bronze-dev-021406833830/bgg/ --recursive --region ap-southeast-2 | Measure-Object).Count
$silverCount = (aws s3 ls s3://boardgames-sommelier-silver-dev-021406833830/bgg/ --recursive --region ap-southeast-2 | Measure-Object).Count
$goldCount = (aws s3 ls s3://boardgames-sommelier-gold-dev-021406833830/bgg/ --recursive --region ap-southeast-2 | Measure-Object).Count
Write-Host "   Bronze files: $bronzeCount" -ForegroundColor $(if($bronzeCount -gt 0){"Green"}else{"Red"})
Write-Host "   Silver files: $silverCount" -ForegroundColor $(if($silverCount -gt 0){"Green"}else{"Red"})
Write-Host "   Gold files: $goldCount" -ForegroundColor $(if($goldCount -gt 0){"Green"}else{"Red"})

# 3. Check Glue tables
Write-Host "`n3. Glue Catalog Tables:" -ForegroundColor Yellow
$tableCount = (aws glue get-tables --database-name boardgames_sommelier_bgg_database --region ap-southeast-2 | ConvertFrom-Json).TableList.Count
Write-Host "   Total tables: $tableCount" -ForegroundColor $(if($tableCount -gt 10){"Green"}else{"Yellow"})

# 4. Query game count
Write-Host "`n4. Game Data Count:" -ForegroundColor Yellow
$queryId = (aws athena start-query-execution --query-string "SELECT COUNT(*) as game_count FROM dim_game" --query-execution-context Database=boardgames_sommelier_bgg_database --work-group boardgames_sommelier-bgg-workgroup --region ap-southeast-2 | ConvertFrom-Json).QueryExecutionId
Start-Sleep -Seconds 5
$gameCount = (aws athena get-query-results --query-execution-id $queryId --region ap-southeast-2 | ConvertFrom-Json).ResultSet.Rows[1].Data[0].VarCharValue
Write-Host "   Games in dim_game: $gameCount" -ForegroundColor $(if([int]$gameCount -gt 0){"Green"}else{"Red"})

Write-Host "`n=== Validation Complete ===" -ForegroundColor Cyan
```

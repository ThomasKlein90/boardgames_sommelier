{{
    config(
        materialized='view',
        schema='analytics',
        tags=['staging']
    )
}}

WITH source_data AS (
    select
        game_id,
        primary_name as name,
        year as year_published,
        min_players,
        max_players,
        min_time as min_playtime,
        max_time as max_playtime,
        min_age_rec as min_age,
        num_votes_bgg as users_rated,
        avg_rating_bgg as average_rating,
        bayes_rating_bgg as bayes_average,
        complexity_bgg as average_weight,
        extraction_date as extraction_timestamp,
        year AS partition_year
    FROM {{ source('raw','dim_game')}}
    WHERE game_id IS NOT NULL
)

SELECT
    game_id,
    name,
    year_published,
    COALESCE(min_players, 1) AS min_players,
    COALESCE(max_players, min_players, 1) AS max_players,
    COALESCE(min_playtime, 0) AS min_playtime,
    COALESCE(max_playtime, min_playtime, 0) AS max_playtime,
    COALESCE(max_playtime, min_playtime, 0) AS playing_time,
    COALESCE(min_age, 0) AS min_age,
    COALESCE(users_rated, 0) AS users_rated,
    COALESCE(average_rating, 0.0) AS average_rating,
    COALESCE(bayes_average, 0.0) AS bayes_average,
    COALESCE(average_weight, 0.0) AS complexity,
    0 AS popularity_owned,
    0 AS popularity_wishlisted,
    extraction_timestamp,
    partition_year
FROM source_data;
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
        name,
        year_published,
        min_players,
        max_players,
        min_playtime,
        max_playtime,
        playing_time,
        min_age,
        users_rated,
        average_rating,
        bayes_average,
        average_weight,
        owned,
        wishing,
        extraction_timestamp,
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
    COALESCE(playing_time, 0) AS playing_time,
    COALESCE(min_age, 0) AS min_age,
    COALESCE(users_rated, 0) AS users_rated,
    COALESCE(average_rating, 0.0) AS average_rating,
    COALESCE(bayes_average, 0.0) AS bayes_average,
    COALESCE(average_weight, 0.0) AS complexity,
    COALESCE(owned, 0) AS popularity_owned,
    COALESCE(wishing, 0) AS popularity_wishlisted,
    extraction_timestamp,
    partition_year
FROM source_data;
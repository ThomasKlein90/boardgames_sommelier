{{
    config(
        materialized='view',
        schema='analytics',
        tags=['mart', 'ml']
    )
}}

WITH game_base AS (
    SELECT * FROM {{ ref('stg_games') }}
),

game_categories AS (
    SELECT
        game_id,
        COUNT(DISTINCT category_id) AS category_count
    FROM {{ source('raw','br_game_category') }}
    GROUP BY game_id
),

game_mechanics AS (
    SELECT
        game_id,
        COUNT(DISTINCT mechanic_id) AS mechanic_count
    FROM {{ source('raw','br_game_mechanic') }}
    GROUP BY game_id
),

game_themes AS (
    SELECT
        game_id,
        COUNT(DISTINCT theme_id) AS theme_count
    FROM {{ source('raw','br_game_theme') }}
    GROUP BY game_id
)

SELECT
    g.game_id,
    g.name,
    g.year_published,
    g.min_players,
    g.max_players,
    g.min_playtime,
    g.max_playtime,
    g.playing_time,
    g.min_age,
    g.users_rated,
    g.average_rating,
    g.bayes_average,
    g.complexity,
    g.popularity_owned,
    g.popularity_wishlisted,

    -- Features for ML
    COALESCE(c.category_count, 0) AS category_count,
    COALESCE(m.mechanic_count, 0) AS mechanic_count,
    COALESCE(t.theme_count, 0) AS theme_count,

    -- Player count flexibility
    (g.max_players - g.min_players + 1) AS player_count_range,

    -- Categorization
    CASE
        WHEN g.complexity <= 2.0 THEN 'Light'
        WHEN g.complexity <= 3.0 THEN 'Medium-Light'
        WHEN g.complexity <= 3.5 THEN 'Medium'
        WHEN g.complexity <= 4.0 THEN 'Medium-Heavy'
        ELSE 'Heavy'
    END AS complexity_category,

    CASE
        WHEN g.playing_time <= 30 THEN 'Short'
        WHEN g.playing_time <= 60 THEN 'Medium'
        WHEN g.playing_time <= 120 THEN 'Long'
        ELSE 'Very Long'
    END AS playtime_category,

    CASE
        WHEN g.users_rated < 100 THEN 'Niche'
        WHEN g.users_rated < 1000 THEN 'Moderate'
        WHEN g.users_rated < 10000 THEN 'Popular'
        ELSE 'Very Popular'
    END AS popularity_tier

FROM game_base g
LEFT JOIN game_categories c ON g.game_id = c.game_id
LEFT JOIN game_mechanics m ON g.game_id = m.game_id
LEFT JOIN game_themes t ON g.game_id = t.game_id;
-- DataHub Postgres init schema (v0.14)
-- Source: https://github.com/datahub-project/datahub/blob/master/docker/postgres-setup/init.sql

CREATE TABLE IF NOT EXISTS metadata_aspect_v2 (
    urn                           VARCHAR(500) NOT NULL,
    aspect                        VARCHAR(200) NOT NULL,
    version                       BIGINT       NOT NULL,
    metadata                      TEXT         NOT NULL,
    systemmetadata                TEXT,
    createdon                     TIMESTAMP    NOT NULL,
    createdby                     VARCHAR(255) NOT NULL,
    createdfor                    VARCHAR(255),
    CONSTRAINT pk_metadata_aspect_v2 PRIMARY KEY (urn, aspect, version)
);

CREATE INDEX IF NOT EXISTS timeIndex ON metadata_aspect_v2 (createdon);

CREATE TEMP TABLE temp_metadata_aspect_v2_seed (
    urn            VARCHAR(500),
    aspect         VARCHAR(200),
    version        BIGINT,
    metadata       TEXT,
    systemmetadata TEXT,
    createdon      TIMESTAMP,
    createdby      VARCHAR(255)
);

INSERT INTO temp_metadata_aspect_v2_seed VALUES
    ('urn:li:corpuser:datahub',
     'corpUserInfo',
     0,
     '{"displayName":"Data Hub","active":true,"fullName":"Data Hub","email":"datahub@datahubproject.io"}',
     NULL,
     NOW(),
     'urn:li:corpuser:__datahub_system'),
    ('urn:li:corpuser:datahub',
     'corpUserEditableInfo',
     0,
     '{"skills":[],"teams":[],"pictureLink":"https://raw.githubusercontent.com/datahub-project/datahub/master/datahub-web-react/src/images/default_avatar.png"}',
     NULL,
     NOW(),
     'urn:li:corpuser:__datahub_system');

INSERT INTO metadata_aspect_v2 (urn, aspect, version, metadata, systemmetadata, createdon, createdby)
SELECT t.urn, t.aspect, t.version, t.metadata, t.systemmetadata, t.createdon, t.createdby
FROM temp_metadata_aspect_v2_seed t
LEFT JOIN metadata_aspect_v2 m
       ON t.urn = m.urn AND t.aspect = m.aspect AND t.version = m.version
WHERE m.urn IS NULL;

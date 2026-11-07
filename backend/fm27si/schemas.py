"""Contrato de dados normalizado.

Os dois conectores (Live Connector e Save Reader) produzem exatamente estes objetos. O
importador só conhece este contrato, nunca o formato de origem.

Regras:
- Um valor que a fonte não fornece fica ``None``. Nunca é preenchido com uma estimativa.
- ``field_status`` regista, por campo, o grau de confiança declarado pela fonte:
  ``verified`` (confirmado contra o ecrã do jogo pela ferramenta de origem),
  ``unconfirmed`` (lido, mas significado não confirmado no FM27),
  ``derived`` (calculado por nós a partir de valores lidos, p.ex. época a partir da data),
  ``estimate`` (estimativa — reservado; a PoC não produz nenhuma).
- A origem e a data de cada dado ficam no ``SourceInfo`` do lote.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FieldStatus = Literal["verified", "unconfirmed", "derived", "estimate"]
ConnectorKind = Literal["live_memory", "save_file", "synthetic"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceInfo(_Model):
    connector: ConnectorKind
    tool: str = Field(description="Ferramenta que leu o jogo, p.ex. 'FMSuperScout scanner v1.7.3'")
    tool_version: str | None = None
    source_path: str | None = None
    source_sha256: str | None = None
    source_mtime: datetime | None = None
    read_at: datetime = Field(description="Quando a fonte foi gerada/lida")
    game: str | None = None  # "FM27"
    game_version: str | None = None
    game_version_supported: bool | None = None
    game_date: date | None = None
    game_date_status: FieldStatus = "unconfirmed"
    currency: str | None = None  # unidade monetária tal como guardada
    synthetic: bool = False  # True para dados de teste fabricados


class CareerInfo(_Model):
    manager_name: str | None = None
    managed_club: str | None = None
    save_name: str | None = None


class ClubRef(_Model):
    source_uid: int | None = None
    unique_id: int | None = None
    name: str | None = None
    short_name: str | None = None
    reputation: int | None = None
    division: str | None = None


class ClubRecord(ClubRef):
    nation_id: int | None = None
    last_league_position: int | None = None


class Contract(_Model):
    wage_weekly: int | None = None
    start: date | None = None
    expires: date | None = None
    squad_status: str | None = None
    transfer_listed: bool | None = None
    loan_listed: bool | None = None
    not_for_sale: bool | None = None
    set_for_release: bool | None = None
    on_loan: bool | None = None
    loan_parent_club: str | None = None
    loan_end: date | None = None


class SeasonStats(_Model):
    season: str | None = None  # p.ex. "2026" (ano de início, como guardado)
    competition_kind: str
    club_name: str | None = None
    starts: int | None = None
    sub_appearances: int | None = None
    minutes: int | None = None
    goals: int | None = None
    assists: int | None = None
    average_rating: float | None = None
    player_of_the_match: int | None = None
    expected_goals: float | None = None
    expected_assists: float | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    clean_sheets: int | None = None
    extra: dict[str, float | int | None] = Field(default_factory=dict)


class NormalizedPlayer(_Model):
    source_uid: int = Field(description="Id do registo na fonte")
    unique_id: int | None = Field(None, description="Unique ID da base de dados do FM")
    name: str
    first_name: str | None = None
    last_name: str | None = None
    common_name: str | None = None
    birth_date: date | None = None
    birth_year: int | None = None
    age: int | None = None
    gender: Literal["male", "female"] | None = None
    nationalities: list[str] = Field(default_factory=list)
    nation_ids: list[int] = Field(default_factory=list)
    height_cm: int | None = None
    foot_left: int | None = None
    foot_right: int | None = None
    preferred_foot: str | None = None

    ca: int | None = None
    pa: int | None = None
    pa_range_code: int | None = None  # PA negativo (intervalo) quando a fonte não tem PA fixo

    reputation_home: int | None = None
    reputation_current: int | None = None
    reputation_world: int | None = None

    club: ClubRef | None = None
    contract: Contract | None = None
    market_value: int | None = None

    positions: dict[str, int] = Field(default_factory=dict)  # 1..20 por posição
    natural_positions: list[str] = Field(default_factory=list)
    accomplished_positions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)

    attributes: dict[str, int] = Field(default_factory=dict)  # chaves de catalog.ATTRIBUTES
    traits: list[str] = Field(default_factory=list)
    season_stats: list[SeasonStats] = Field(default_factory=list)

    field_status: dict[str, FieldStatus] = Field(default_factory=dict)
    extra: dict[str, object] = Field(default_factory=dict)


class ImportBundle(_Model):
    source: SourceInfo
    career: CareerInfo
    players: list[NormalizedPlayer]
    clubs: list[ClubRecord] = Field(default_factory=list)
    unavailable_fields: list[str] = Field(
        default_factory=list, description="Campos do contrato que esta fonte não fornece"
    )
    warnings: list[str] = Field(default_factory=list)

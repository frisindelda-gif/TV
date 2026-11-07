"""Modelo relacional (SQLAlchemy 2.0).

Separação essencial: ``Player`` é a identidade estável dentro de uma carreira; cada
importação cria uma ``PlayerSnapshot`` com os valores *naquele momento*. O histórico de
evolução é simplesmente a série de snapshots de um jogador.

Cada snapshot aponta para o ``ImportRun`` que a produziu, que guarda a origem (conector,
ferramenta, ficheiro, hash) e as datas (data real da leitura e data no jogo).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Career(Base):
    __tablename__ = "careers"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(300), unique=True)
    label: Mapped[str] = mapped_column(String(300))
    game: Mapped[str | None] = mapped_column(String(20))
    manager_name: Mapped[str | None] = mapped_column(String(200))
    save_name: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    runs: Mapped[list[ImportRun]] = relationship(back_populates="career")


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"))
    connector: Mapped[str] = mapped_column(String(30))  # live_memory | save_file
    tool: Mapped[str] = mapped_column(String(200))
    tool_version: Mapped[str | None] = mapped_column(String(50))
    source_path: Mapped[str | None] = mapped_column(Text)
    source_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    source_mtime: Mapped[datetime | None] = mapped_column(DateTime)
    read_at: Mapped[datetime] = mapped_column(DateTime)  # quando a fonte foi gerada
    imported_at: Mapped[datetime] = mapped_column(DateTime)  # quando entrou na BD
    game: Mapped[str | None] = mapped_column(String(20))
    game_version: Mapped[str | None] = mapped_column(String(50))
    game_version_supported: Mapped[bool | None] = mapped_column(Boolean)
    game_date: Mapped[date | None] = mapped_column(Date)
    game_date_status: Mapped[str] = mapped_column(String(20))
    season_label: Mapped[str | None] = mapped_column(String(20))  # derivado da data
    managed_club: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str | None] = mapped_column(String(10))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    player_count: Mapped[int] = mapped_column(Integer, default=0)
    source_player_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    unavailable_fields: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    career: Mapped[Career] = relationship(back_populates="runs")


class Club(Base):
    __tablename__ = "clubs"
    __table_args__ = (UniqueConstraint("career_id", "identity_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"))
    identity_key: Mapped[str] = mapped_column(String(300))  # uid:<n> ou name:<nome>
    unique_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(100))
    reputation: Mapped[int | None] = mapped_column(Integer)
    division: Mapped[str | None] = mapped_column(String(200))
    nation_id: Mapped[int | None] = mapped_column(Integer)
    last_seen_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"))


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("career_id", "identity_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    career_id: Mapped[int] = mapped_column(ForeignKey("careers.id", ondelete="CASCADE"))
    # "uid:<Unique ID>" quando a fonte o dá; caso contrário "src:<conector>:<id>:<nascimento>".
    identity_key: Mapped[str] = mapped_column(String(200))
    unique_id: Mapped[int | None] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(10))
    nationalities: Mapped[list] = mapped_column(JSON, default=list)
    first_seen_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))
    last_seen_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))

    snapshots: Mapped[list[PlayerSnapshot]] = relationship(
        back_populates="player", order_by="PlayerSnapshot.id", cascade="all, delete-orphan"
    )


class PlayerSnapshot(Base):
    __tablename__ = "player_snapshots"
    __table_args__ = (
        UniqueConstraint("player_id", "run_id"),
        Index("ix_snap_run_ca", "run_id", "ca"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), index=True)
    source_uid: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(Integer)
    ca: Mapped[int | None] = mapped_column(Integer)
    pa: Mapped[int | None] = mapped_column(Integer)
    pa_range_code: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    foot_left: Mapped[int | None] = mapped_column(Integer)
    foot_right: Mapped[int | None] = mapped_column(Integer)
    preferred_foot: Mapped[str | None] = mapped_column(String(20))
    reputation_home: Mapped[int | None] = mapped_column(Integer)
    reputation_current: Mapped[int | None] = mapped_column(Integer)
    reputation_world: Mapped[int | None] = mapped_column(Integer)
    club_id: Mapped[int | None] = mapped_column(ForeignKey("clubs.id"))
    club_name: Mapped[str | None] = mapped_column(String(200))
    division: Mapped[str | None] = mapped_column(String(200))
    market_value: Mapped[int | None] = mapped_column(Integer)
    wage_weekly: Mapped[int | None] = mapped_column(Integer)
    contract_start: Mapped[date | None] = mapped_column(Date)
    contract_expires: Mapped[date | None] = mapped_column(Date)
    contract: Mapped[dict | None] = mapped_column(JSON)
    positions: Mapped[dict] = mapped_column(JSON, default=dict)
    natural_positions: Mapped[list] = mapped_column(JSON, default=list)
    accomplished_positions: Mapped[list] = mapped_column(JSON, default=list)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    traits: Mapped[list] = mapped_column(JSON, default=list)
    field_status: Mapped[dict] = mapped_column(JSON, default=dict)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    quality: Mapped[str] = mapped_column(String(10), default="ok")  # ok | warning | error

    player: Mapped[Player] = relationship(back_populates="snapshots")
    issues: Mapped[list[ValidationIssue]] = relationship(cascade="all, delete-orphan")
    season_stats: Mapped[list[SeasonStatLine]] = relationship(cascade="all, delete-orphan")


def _attribute_columns() -> dict:
    from fm27si.catalog import ATTRIBUTES  # noqa: PLC0415

    return {k: mapped_column(Integer, nullable=True) for k in ATTRIBUTES}


# Tabela larga: uma coluna por atributo do catálogo, uma linha por snapshot. Em SQLite isto
# é ~60x menos linhas que um modelo chave/valor, filtra com índices normais
# (``pace >= 15``) e o histórico é um JOIN simples. NULL = a fonte não forneceu o atributo.
SnapshotAttributes = type(
    "SnapshotAttributes",
    (Base,),
    {
        "__tablename__": "snapshot_attributes",
        "__doc__": "Atributos (52 + 8 de personalidade) de um snapshot.",
        "snapshot_id": mapped_column(ForeignKey("player_snapshots.id", ondelete="CASCADE"), primary_key=True),
        "__annotations__": {},
        **_attribute_columns(),
    },
)


class SeasonStatLine(Base):
    __tablename__ = "season_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("player_snapshots.id", ondelete="CASCADE"), index=True)
    season: Mapped[str | None] = mapped_column(String(20))
    competition_kind: Mapped[str] = mapped_column(String(40))
    club_name: Mapped[str | None] = mapped_column(String(200))
    starts: Mapped[int | None] = mapped_column(Integer)
    sub_appearances: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    average_rating: Mapped[float | None] = mapped_column(Float)
    player_of_the_match: Mapped[int | None] = mapped_column(Integer)
    expected_goals: Mapped[float | None] = mapped_column(Float)
    expected_assists: Mapped[float | None] = mapped_column(Float)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)
    clean_sheets: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class ValidationIssue(Base):
    __tablename__ = "validation_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("player_snapshots.id", ondelete="CASCADE"), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    field: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[object | None] = mapped_column(JSON)

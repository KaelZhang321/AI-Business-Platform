from fastapi import FastAPI, Query
from sqlalchemy import create_engine, text, URL
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import quote_plus

app = FastAPI(title="Dify Table API")

# ====== 修改成你自己的数据库信息 ======
DB_HOST = "rm-2ze7k76808sos442l.mysql.rds.aliyuncs.com"
DB_PORT = 3306
DB_USER = "ai_platform_business_dev_0328"
DB_PASSWORD = "%ea2b0FWCIa6VNFO"
DB_NAME = "uat_ai_platform_business"

DATABASE_URL = URL.create(
    "mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    query={"charset": "utf8mb4"}
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)


@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/api/test")
def test_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"success": True, "message": "Database connected"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/deal_project")
def get_deal_project(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0)
):
    try:
        sql = text("""
            SELECT *
            FROM deal_project
            LIMIT :limit OFFSET :offset
        """)

        with engine.connect() as conn:
            result = conn.execute(sql, {"limit": limit, "offset": offset})
            rows = [dict(row._mapping) for row in result]

        return {
            "success": True,
            "table": "deal_project",
            "count": len(rows),
            "data": rows
        }

    except SQLAlchemyError as e:
        return {"success": False, "error": str(e)}


@app.get("/api/deal_connection")
def get_deal_connection(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0)
):
    try:
        sql = text("""
            SELECT *
            FROM deal_connection
            LIMIT :limit OFFSET :offset
        """)

        with engine.connect() as conn:
            result = conn.execute(sql, {"limit": limit, "offset": offset})
            rows = [dict(row._mapping) for row in result]

        return {
            "success": True,
            "table": "deal_connection",
            "count": len(rows),
            "data": rows
        }

    except SQLAlchemyError as e:
        return {"success": False, "error": str(e)}


@app.get("/api/query")
def query_all_tables(keyword: str):
    try:
        kw = f"%{keyword}%"

        with engine.connect() as conn:
            sql_project = text("""
                SELECT *, 'deal_project' AS source_table
                FROM deal_project
                WHERE 项目名称 LIKE :kw
                   OR 所属系统 LIKE :kw
                   OR 适应症 LIKE :kw
                   OR 关注指标 LIKE :kw
            """)

            project_rows = conn.execute(sql_project, {"kw": kw}).fetchall()

            sql_connection = text("""
                SELECT *, 'deal_connection' AS source_table
                FROM deal_connection
                WHERE 项目名称 LIKE :kw
                   OR 所属系统 LIKE :kw
                   OR 适应症 LIKE :kw
                   OR 关注指标 LIKE :kw
            """)

            connection_rows = conn.execute(sql_connection, {"kw": kw}).fetchall()

        rows = [dict(row._mapping) for row in project_rows + connection_rows]

        return {
            "success": True,
            "keyword": keyword,
            "count": len(rows),
            "data": rows
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
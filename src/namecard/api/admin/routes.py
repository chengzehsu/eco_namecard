"""
Admin Panel Routes

Provides web routes for tenant management, authentication, and statistics.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import structlog

from src.namecard.api.admin.auth import login_required, get_admin_auth
from src.namecard.core.services.tenant_service import get_tenant_service
from src.namecard.core.models.tenant import TenantCreateRequest, TenantUpdateRequest

logger = structlog.get_logger()

# Calculate absolute paths for templates and static files
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "../../../.."))

# Create blueprint
admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder=os.path.join(_project_root, "templates/admin"),
    static_folder=os.path.join(_project_root, "static/admin"),
)


# ==================== Authentication Routes ====================


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        auth = get_admin_auth()
        admin = auth.authenticate(username, password)

        if admin:
            auth.login(admin)
            flash("登入成功", "success")
            return redirect(url_for("admin.dashboard"))
        else:
            flash("帳號或密碼錯誤", "error")

    return render_template("login.html")


@admin_bp.route("/logout")
def logout():
    """Admin logout"""
    auth = get_admin_auth()
    auth.logout()
    flash("已登出", "info")
    return redirect(url_for("admin.login"))


# ==================== Dashboard ====================


@admin_bp.route("/")
@login_required
def dashboard():
    """Admin dashboard with overview statistics"""
    # Get time period from query parameters
    period = request.args.get("period", "day")  # day, week, month
    days_map = {"day": 1, "week": 7, "month": 30}
    days = days_map.get(period, 1)

    tenant_service = get_tenant_service()
    stats = tenant_service.get_overall_stats()
    tenants = tenant_service.list_tenants(include_inactive=True)

    # Get extended stats for the period (with default values)
    all_tenants_summary = tenant_service.get_all_tenants_summary(days=days) or {
        "total_processed": 0,
        "total_saved": 0,
        "total_errors": 0,
        "active_tenants": 0,
    }

    try:
        tenant_stats = tenant_service.get_today_stats_by_tenant() or {}
    except Exception as e:
        logger.warning("Failed to get tenant stats", error=str(e))
        tenant_stats = {}

    return render_template(
        "dashboard.html",
        stats=stats,
        tenants=tenants,
        tenant_stats=tenant_stats,
        all_tenants_summary=all_tenants_summary,
        current_period=period,
        admin_username=session.get("admin_username"),
    )


# ==================== Tenant Management ====================


@admin_bp.route("/tenants")
@login_required
def list_tenants():
    """List all tenants"""
    tenant_service = get_tenant_service()
    tenants = tenant_service.list_tenants(include_inactive=True)

    return render_template(
        "tenants/list.html", tenants=tenants, admin_username=session.get("admin_username")
    )


@admin_bp.route("/tenants/new", methods=["GET", "POST"])
@login_required
def create_tenant():
    """Create new tenant"""
    if request.method == "POST":
        try:
            from simple_config import settings
            from pydantic import ValidationError

            # Read checkbox values
            auto_create_notion_db = request.form.get("auto_create_notion_db") == "on"
            use_shared_notion_api = request.form.get("use_shared_notion_api") == "on"
            use_shared_google_api = request.form.get("use_shared_google_api") == "on"

            tenant_name = request.form.get("name", "").strip()

            # ========== 前置驗證 ==========
            # 1. 驗證必填欄位
            if not tenant_name:
                flash("請填寫租戶名稱", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )

            # 2. 驗證 LINE 憑證
            line_access_token = request.form.get("line_channel_access_token", "").strip()
            line_secret = request.form.get("line_channel_secret", "").strip()
            if not line_access_token:
                flash("請填寫 LINE Channel Access Token", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )
            if not line_secret:
                flash("請填寫 LINE Channel Secret", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )

            # 3. 驗證 Bot User ID（必須已透過按鈕獲取）
            line_channel_id = request.form.get("line_channel_id", "").strip()

            # Bot User ID 必須存在且以 U 開頭
            if not line_channel_id:
                flash("請先點擊「獲取 Bot User ID」按鈕獲取 Bot User ID", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )

            if not line_channel_id.startswith("U"):
                flash("LINE Bot User ID 格式不正確，必須以 U 開頭。請重新點擊「獲取 Bot User ID」按鈕。", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )

            logger.info("BOT_USER_ID_VALIDATED", bot_user_id=line_channel_id)

            # 4. 驗證 Notion API Key
            if use_shared_notion_api:
                notion_api_key = settings.notion_api_key
                if not notion_api_key:
                    flash("系統共用 Notion API Key 尚未設定，請聯繫管理員或取消勾選「使用共用 API Key」", "error")
                    return render_template(
                        "tenants/form.html",
                        tenant=None,
                        is_edit=False,
                        admin_username=session.get("admin_username"),
                    )
            else:
                notion_api_key = request.form.get("notion_api_key", "").strip()
                if not notion_api_key:
                    flash("請提供 Notion API Key 或勾選使用共用 API Key", "error")
                    return render_template(
                        "tenants/form.html",
                        tenant=None,
                        is_edit=False,
                        admin_username=session.get("admin_username"),
                    )

            # 4. 驗證自動建立 Notion DB 的前提條件
            if auto_create_notion_db:
                if not settings.notion_shared_parent_page_id:
                    flash("系統共用 Parent Page ID 尚未設定，無法自動創建資料庫", "error")
                    return render_template(
                        "tenants/form.html",
                        tenant=None,
                        is_edit=False,
                        admin_username=session.get("admin_username"),
                    )

            # Determine Notion Database ID
            notion_database_id = request.form.get("notion_database_id", "").strip()

            if auto_create_notion_db:
                # Auto-create Notion database
                from src.namecard.infrastructure.storage.notion_client import NotionClient

                logger.info(
                    "Auto-creating Notion database for tenant",
                    tenant_name=tenant_name,
                    use_shared_notion_api=use_shared_notion_api,
                    parent_page_id=settings.notion_shared_parent_page_id,
                )

                try:
                    created_db_id = NotionClient.create_database(
                        api_key=notion_api_key,
                        tenant_name=tenant_name,
                        parent_page_id=settings.notion_shared_parent_page_id,
                    )
                except Exception as notion_err:
                    logger.error("Notion database creation failed", error=str(notion_err))
                    flash(f"無法創建 Notion 資料庫: {str(notion_err)}", "error")
                    return render_template(
                        "tenants/form.html",
                        tenant=None,
                        is_edit=False,
                        admin_username=session.get("admin_username"),
                    )

                if not created_db_id:
                    flash(
                        "無法創建 Notion 資料庫，請檢查：\n1. Notion API Key 是否有效\n2. Parent Page 是否已分享給 Integration",
                        "error",
                    )
                    return render_template(
                        "tenants/form.html",
                        tenant=None,
                        is_edit=False,
                        admin_username=session.get("admin_username"),
                    )

                notion_database_id = created_db_id
                logger.info("Notion database created successfully", database_id=created_db_id)

            elif not notion_database_id:
                flash("請提供 Notion Database ID 或勾選自動創建", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )

            # Build tenant request (with pre-validated data)
            try:
                tenant_request = TenantCreateRequest(
                    name=tenant_name,
                    slug=request.form.get("slug", "").strip() or None,
                    line_channel_id=line_channel_id,  # 使用自動獲取或用戶填入的值
                    line_channel_access_token=line_access_token,
                    line_channel_secret=line_secret,
                    notion_api_key=notion_api_key if not use_shared_notion_api else None,
                    notion_database_id=notion_database_id,
                    use_shared_notion_api=use_shared_notion_api,
                    auto_create_notion_db=auto_create_notion_db,
                    google_api_key=request.form.get("google_api_key", "").strip() or None,
                    use_shared_google_api=use_shared_google_api,
                    daily_card_limit=int(request.form.get("daily_card_limit", 50) or 50),
                    batch_size_limit=int(request.form.get("batch_size_limit", 10) or 10),
                )
            except ValidationError as ve:
                # Pydantic validation error - provide user-friendly message
                error_msgs = []
                for err in ve.errors():
                    field = err.get("loc", ["unknown"])[0]
                    msg = err.get("msg", "驗證失敗")
                    error_msgs.append(f"{field}: {msg}")
                flash(f"表單驗證失敗: {'; '.join(error_msgs)}", "error")
                return render_template(
                    "tenants/form.html",
                    tenant=None,
                    is_edit=False,
                    admin_username=session.get("admin_username"),
                )

            tenant_service = get_tenant_service()
            tenant = tenant_service.create_tenant(tenant_request)

            if auto_create_notion_db:
                flash(f"租戶 '{tenant.name}' 建立成功，Notion 資料庫已自動創建", "success")
            else:
                flash(f"租戶 '{tenant.name}' 建立成功", "success")
            return redirect(url_for("admin.list_tenants"))

        except ValidationError as ve:
            # Catch any remaining Pydantic errors
            logger.error("Validation error creating tenant", error=str(ve))
            flash(f"資料驗證失敗: {str(ve)}", "error")
        except Exception as e:
            import traceback

            logger.error("Failed to create tenant", error=str(e), traceback=traceback.format_exc())
            # Provide more user-friendly error messages
            error_msg = str(e)
            if "UNIQUE constraint failed" in error_msg:
                if "line_channel_id" in error_msg:
                    flash("此 LINE Bot User ID 已被其他租戶使用", "error")
                elif "slug" in error_msg:
                    flash("此識別碼 (Slug) 已被使用，請使用其他名稱", "error")
                else:
                    flash(f"資料重複: {error_msg}", "error")
            elif "NOT NULL constraint failed" in error_msg:
                flash(f"必填欄位不可為空: {error_msg}", "error")
            else:
                flash(f"建立失敗: {error_msg}", "error")

    return render_template(
        "tenants/form.html",
        tenant=None,
        is_edit=False,
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/tenants/<tenant_id>", methods=["GET", "POST"])
@login_required
def edit_tenant(tenant_id: str):
    """Edit existing tenant"""
    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)

    if not tenant:
        flash("找不到此租戶", "error")
        return redirect(url_for("admin.list_tenants"))

    if request.method == "POST":
        try:
            # Build update request (only include changed fields)
            update_data = {}

            name = request.form.get("name", "").strip()
            if name and name != tenant.name:
                update_data["name"] = name

            is_active = request.form.get("is_active") == "on"
            if is_active != tenant.is_active:
                update_data["is_active"] = is_active

            # Credential fields - only update if provided
            line_token = request.form.get("line_channel_access_token", "").strip()
            if line_token:
                update_data["line_channel_access_token"] = line_token

            line_secret = request.form.get("line_channel_secret", "").strip()
            if line_secret:
                update_data["line_channel_secret"] = line_secret

            notion_key = request.form.get("notion_api_key", "").strip()
            if notion_key:
                update_data["notion_api_key"] = notion_key

            notion_db = request.form.get("notion_database_id", "").strip()
            if notion_db and notion_db != tenant.notion_database_id:
                update_data["notion_database_id"] = notion_db

            google_key = request.form.get("google_api_key", "").strip()
            if google_key:
                update_data["google_api_key"] = google_key

            use_shared = request.form.get("use_shared_google_api") == "on"
            if use_shared != tenant.use_shared_google_api:
                update_data["use_shared_google_api"] = use_shared

            daily_limit = int(request.form.get("daily_card_limit", 50))
            if daily_limit != tenant.daily_card_limit:
                update_data["daily_card_limit"] = daily_limit

            batch_limit = int(request.form.get("batch_size_limit", 10))
            if batch_limit != tenant.batch_size_limit:
                update_data["batch_size_limit"] = batch_limit

            if update_data:
                update_request = TenantUpdateRequest(**update_data)
                updated_tenant = tenant_service.update_tenant(tenant_id, update_request)

                # Show verification for critical fields
                if "notion_database_id" in update_data:
                    flash(
                        f"✓ 租戶更新成功 - Notion DB ID: {updated_tenant.notion_database_id[:10]}...",
                        "success",
                    )
                else:
                    flash("租戶更新成功", "success")
            else:
                flash("沒有變更", "info")

            return redirect(url_for("admin.list_tenants"))

        except Exception as e:
            logger.error("Failed to update tenant", error=str(e))
            flash(f"更新失敗: {str(e)}", "error")

    return render_template(
        "tenants/form.html",
        tenant=tenant,
        is_edit=True,
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/tenants/<tenant_id>/delete", methods=["POST"])
@login_required
def delete_tenant(tenant_id: str):
    """Delete (deactivate) a tenant"""
    tenant_service = get_tenant_service()

    # Soft delete by default
    hard_delete = request.form.get("hard_delete") == "true"
    result = tenant_service.delete_tenant(tenant_id, soft_delete=not hard_delete)

    if result:
        action = "永久刪除" if hard_delete else "停用"
        flash(f"租戶已{action}", "success")
    else:
        flash("找不到此租戶", "error")

    return redirect(url_for("admin.list_tenants"))


@admin_bp.route("/tenants/<tenant_id>/activate", methods=["POST"])
@login_required
def activate_tenant(tenant_id: str):
    """Reactivate a deactivated tenant"""
    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)

    if not tenant:
        flash("找不到此租戶", "error")
        return redirect(url_for("admin.list_tenants"))

    # Update is_active to True
    update_request = TenantUpdateRequest(is_active=True)
    tenant_service.update_tenant(tenant_id, update_request)
    flash(f"租戶 '{tenant.name}' 已重新啟用", "success")

    return redirect(url_for("admin.list_tenants"))


@admin_bp.route("/tenants/<tenant_id>/stats")
@login_required
def tenant_stats(tenant_id: str):
    """View tenant statistics"""
    # Get time range from query parameters
    period = request.args.get("period", "month")  # day, week, month, year
    days_map = {"day": 1, "week": 7, "month": 30, "year": 365}
    days = days_map.get(period, 30)

    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)

    if not tenant:
        flash("找不到此租戶", "error")
        return redirect(url_for("admin.list_tenants"))

    # Get comprehensive stats (with default values to prevent None errors)
    stats = tenant_service.get_tenant_stats(tenant_id, days=days) or []
    summary = tenant_service.get_tenant_stats_summary(tenant_id, days=days) or {
        "total_processed": 0,
        "total_saved": 0,
        "total_errors": 0,
        "total_api_calls": 0,
        "active_days": 0,
        "avg_daily_processed": 0,
        "success_rate": 0,
        "error_rate": 0,
    }
    monthly_stats = tenant_service.get_tenant_monthly_stats(tenant_id, months=12) or []
    user_count = tenant_service.get_user_count(tenant_id, days=days) or 0
    top_users = tenant_service.get_top_users(tenant_id, limit=10, days=days) or []

    return render_template(
        "tenants/stats.html",
        tenant=tenant,
        stats=stats,
        summary=summary,
        monthly_stats=monthly_stats,
        user_count=user_count,
        top_users=top_users,
        current_period=period,
        admin_username=session.get("admin_username"),
    )


# ==================== API Endpoints ====================


@admin_bp.route("/api/tenants/<tenant_id>/test", methods=["POST"])
@login_required
def test_tenant_connection(tenant_id: str):
    """Test tenant connections (LINE, Notion)"""
    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)

    if not tenant:
        return jsonify({"status": "error", "message": "Tenant not found"}), 404

    results = {
        "line": {"status": "unknown"},
        "notion": {"status": "unknown"},
        "google": {"status": "unknown"},
    }

    # Test LINE Bot API
    try:
        from linebot import LineBotApi

        line_api = LineBotApi(tenant.line_channel_access_token)
        # Get bot info to verify token
        bot_info = line_api.get_bot_info()
        results["line"] = {
            "status": "success",
            "bot_name": bot_info.display_name if hasattr(bot_info, "display_name") else "OK",
        }
    except Exception as e:
        results["line"] = {"status": "error", "message": str(e)}

    # Test Notion API (2025-09-03)
    try:
        from src.namecard.infrastructure.storage.notion_client import create_notion_client

        notion = create_notion_client(tenant.notion_api_key)
        db_info = notion.databases.retrieve(database_id=tenant.notion_database_id)
        
        # 獲取 data_sources (2025-09-03 版本)
        data_sources = db_info.get("data_sources", [])
        
        results["notion"] = {
            "status": "success",
            "database_title": db_info.get("title", [{}])[0].get("plain_text", "OK")
            if db_info.get("title")
            else "OK",
            "data_source_count": len(data_sources),
        }
    except Exception as e:
        results["notion"] = {"status": "error", "message": str(e)}

    # Test Google API (if tenant has custom key)
    if tenant.google_api_key and not tenant.use_shared_google_api:
        try:
            import google.generativeai as genai

            genai.configure(api_key=tenant.google_api_key)
            # 驗證 API key（創建 model 實例來測試）
            _ = genai.GenerativeModel("gemini-1.5-flash")
            results["google"] = {"status": "success", "message": "API key valid"}
        except Exception as e:
            results["google"] = {"status": "error", "message": str(e)}
    else:
        results["google"] = {"status": "skipped", "message": "Using shared API key"}

    return jsonify(results)


@admin_bp.route("/api/stats")
@login_required
def api_stats():
    """Get overall statistics as JSON"""
    tenant_service = get_tenant_service()
    stats = tenant_service.get_overall_stats()
    return jsonify(stats)


# ==================== LINE Bot API ====================


@admin_bp.route("/api/fetch-bot-user-id", methods=["POST"])
@login_required
def fetch_bot_user_id():
    """
    使用 Channel Access Token 獲取 Bot User ID

    這個 API 用於在新增租戶時驗證 LINE 憑證並獲取 Bot User ID。
    """
    try:
        access_token = request.json.get("access_token", "").strip()

        if not access_token:
            return jsonify({"success": False, "error": "請提供 Channel Access Token"}), 400

        # 呼叫 LINE API 獲取 bot info
        from linebot import LineBotApi
        from linebot.exceptions import LineBotApiError

        try:
            line_api = LineBotApi(access_token)
            bot_info = line_api.get_bot_info()

            bot_user_id = bot_info.user_id
            bot_name = bot_info.display_name if hasattr(bot_info, "display_name") else None

            # 驗證 Bot User ID 格式
            if not bot_user_id or not bot_user_id.startswith("U"):
                return jsonify({"success": False, "error": "無法獲取有效的 Bot User ID"}), 400

            logger.info("FETCH_BOT_USER_ID_SUCCESS", bot_user_id=bot_user_id, bot_name=bot_name)

            return jsonify({"success": True, "bot_user_id": bot_user_id, "bot_name": bot_name})

        except LineBotApiError as line_err:
            error_msg = str(line_err)
            if "401" in error_msg or "Invalid" in error_msg.lower():
                error_msg = "Channel Access Token 無效或已過期"
            logger.error("FETCH_BOT_USER_ID_LINE_ERROR", error=str(line_err))
            return jsonify({"success": False, "error": error_msg}), 400

    except Exception as e:
        logger.error("FETCH_BOT_USER_ID_ERROR", error=str(e))
        return jsonify({"success": False, "error": f"獲取失敗: {str(e)}"}), 500


@admin_bp.route("/api/fetch-notion-database-info", methods=["POST"])
@login_required
def fetch_notion_database_info():
    """
    驗證 Notion API Key 和 Database ID，取得資料庫名稱

    用於在新增/編輯租戶時驗證 Notion 設定
    """
    try:
        # 取得參數
        notion_api_key = request.json.get("notion_api_key", "").strip()
        database_id = request.json.get("database_id", "").strip()
        use_shared_api = request.json.get("use_shared_api", False)

        # 如果使用共用 API Key
        if use_shared_api:
            from simple_config import settings

            notion_api_key = settings.notion_api_key
            if not notion_api_key:
                return jsonify({"success": False, "error": "系統共用 Notion API Key 尚未設定"}), 400

        # 驗證必填欄位
        if not notion_api_key:
            return jsonify({"success": False, "error": "請提供 Notion API Key 或勾選使用共用 API Key"}), 400

        if not database_id:
            return jsonify({"success": False, "error": "請提供 Notion Database ID"}), 400

        # 呼叫 Notion API (2025-09-03)
        from src.namecard.infrastructure.storage.notion_client import create_notion_client

        try:
            notion = create_notion_client(notion_api_key)
            db_info = notion.databases.retrieve(database_id=database_id)

            # 取得資料庫標題
            db_title = "未命名資料庫"
            if db_info.get("title") and len(db_info["title"]) > 0:
                db_title = db_info["title"][0].get("plain_text", "未命名資料庫")

            # 取得資料庫 URL
            db_url = db_info.get("url", "")
            
            # 2025-09-03: 獲取 data_source_id 和 schema
            data_sources = db_info.get("data_sources", [])
            data_source_id = data_sources[0].get("id") if data_sources else None
            
            # 從 data_source 獲取 properties (2025-09-03)
            properties = {}
            if data_source_id:
                ds_info = notion.request(
                    method="get",
                    path=f"data_sources/{data_source_id}",
                )
                properties = ds_info.get("properties", {})

            # 驗證必要欄位（Name, Email, 公司名稱, 電話）
            required_fields = ["Name", "Email", "公司名稱", "電話"]
            missing_fields = [f for f in required_fields if f not in properties]

            # 取得實際欄位列表（用於 debug）
            actual_fields = list(properties.keys())

            logger.info(
                "FETCH_NOTION_DB_SUCCESS",
                database_id=database_id[:15] + "..." if len(database_id) > 15 else database_id,
                data_source_id=data_source_id[:15] + "..." if data_source_id else None,
                database_title=db_title,
                has_all_required_fields=len(missing_fields) == 0,
                actual_field_count=len(actual_fields),
                actual_fields=actual_fields[:10],  # 只記錄前 10 個
            )

            result = {
                "success": True,
                "database_title": db_title,
                "database_url": db_url,
                "database_id": database_id,
                "data_source_id": data_source_id,  # 2025-09-03
                "actual_fields": actual_fields,  # 顯示實際讀取到的欄位
                "field_count": len(actual_fields),
            }

            # 如果有缺少欄位，發出警告但不阻止
            if missing_fields:
                result["warning"] = f"資料庫缺少建議欄位: {', '.join(missing_fields)}"
                result["debug_info"] = f"實際讀取到 {len(actual_fields)} 個欄位"

            return jsonify(result)

        except Exception as notion_err:
            error_msg = str(notion_err)

            # 根據錯誤類型提供友善訊息
            if "Could not find database" in error_msg:
                error_msg = "找不到此資料庫 ID，請確認：\n1. Database ID 是否正確\n2. 該資料庫是否已分享給 Integration"
            elif "Unauthorized" in error_msg or "401" in error_msg:
                error_msg = "Notion API Key 無效或已過期"
            elif "invalid_request" in error_msg:
                error_msg = "Database ID 格式不正確"

            logger.error(
                "FETCH_NOTION_DB_ERROR",
                error=str(notion_err),
                database_id=database_id[:15] + "..." if database_id else None,
            )

            return jsonify({"success": False, "error": error_msg}), 400

    except Exception as e:
        logger.error("FETCH_NOTION_DB_EXCEPTION", error=str(e))
        return jsonify({"success": False, "error": f"驗證失敗: {str(e)}"}), 500


# ==================== Extended Statistics API ====================


@admin_bp.route("/api/tenants/<tenant_id>/stats/summary")
@login_required
def api_tenant_stats_summary(tenant_id: str):
    """Get tenant statistics summary with calculated metrics"""
    days = request.args.get("days", 30, type=int)
    tenant_service = get_tenant_service()

    tenant = tenant_service.get_tenant_by_id(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    summary = tenant_service.get_tenant_stats_summary(tenant_id, days)
    return jsonify(summary)


@admin_bp.route("/api/tenants/<tenant_id>/stats/daily")
@login_required
def api_tenant_stats_daily(tenant_id: str):
    """Get daily statistics for a tenant (for charts)"""
    days = request.args.get("days", 30, type=int)
    tenant_service = get_tenant_service()

    tenant = tenant_service.get_tenant_by_id(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    stats = tenant_service.get_tenant_stats(tenant_id, days)
    return jsonify(stats)


@admin_bp.route("/api/tenants/<tenant_id>/stats/monthly")
@login_required
def api_tenant_stats_monthly(tenant_id: str):
    """Get monthly aggregated statistics for a tenant"""
    months = request.args.get("months", 12, type=int)
    tenant_service = get_tenant_service()

    tenant = tenant_service.get_tenant_by_id(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    stats = tenant_service.get_tenant_monthly_stats(tenant_id, months)
    return jsonify(stats)


@admin_bp.route("/api/tenants/<tenant_id>/stats/yearly")
@login_required
def api_tenant_stats_yearly(tenant_id: str):
    """Get yearly aggregated statistics for a tenant"""
    years = request.args.get("years", 3, type=int)
    tenant_service = get_tenant_service()

    tenant = tenant_service.get_tenant_by_id(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    stats = tenant_service.get_tenant_yearly_stats(tenant_id, years)
    return jsonify(stats)


@admin_bp.route("/api/tenants/<tenant_id>/users")
@login_required
def api_tenant_users(tenant_id: str):
    """Get user statistics for a tenant"""
    days = request.args.get("days", 30, type=int)
    limit = request.args.get("limit", 20, type=int)
    tenant_service = get_tenant_service()

    tenant = tenant_service.get_tenant_by_id(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    users = tenant_service.get_top_users(tenant_id, limit, days)
    user_count = tenant_service.get_user_count(tenant_id, days)

    return jsonify({"users": users, "total_users": user_count})


# ==================== Google Drive API ====================


@admin_bp.route("/api/drive/fetch-folder", methods=["POST"])
@login_required
def fetch_drive_folder():
    """
    驗證 Google Drive 資料夾並取得資訊
    
    用於在租戶編輯頁面驗證資料夾存取權限
    """
    try:
        folder_url = request.json.get("folder_url", "").strip()
        
        if not folder_url:
            return jsonify({"success": False, "error": "請提供 Google Drive 資料夾網址"}), 400
        
        from src.namecard.infrastructure.storage.google_drive_client import (
            GoogleDriveClient,
            get_google_drive_client,
        )
        
        drive_client = get_google_drive_client()
        
        if not drive_client:
            return jsonify({
                "success": False,
                "error": "Google Drive 服務未設定。請在環境變數中設定 GOOGLE_SERVICE_ACCOUNT_JSON",
                "need_setup": True,
            }), 400
        
        # Validate folder access
        success, message, folder_info = drive_client.validate_folder_access(folder_url)
        
        if success:
            logger.info(
                "DRIVE_FOLDER_VALIDATED",
                folder_id=folder_info.get("id"),
                folder_name=folder_info.get("name"),
                total_files=folder_info.get("total_files"),
            )
            return jsonify({
                "success": True,
                "message": message,
                "folder_name": folder_info.get("name"),
                "folder_id": folder_info.get("id"),
                "total_files": folder_info.get("total_files"),
                "unprocessed_files": folder_info.get("unprocessed_files"),
                "service_account_email": drive_client.service_account_email,
            })
        else:
            return jsonify({
                "success": False,
                "error": message,
                "service_account_email": drive_client.service_account_email,
            }), 400
            
    except Exception as e:
        logger.error("DRIVE_FETCH_FOLDER_ERROR", error=str(e))
        return jsonify({"success": False, "error": f"驗證失敗: {str(e)}"}), 500


@admin_bp.route("/api/drive/sync/<tenant_id>", methods=["POST"])
@login_required
def start_drive_sync(tenant_id: str):
    """
    開始 Google Drive 同步處理
    
    這會在背景執行批次處理，前端可透過 sync-status 輪詢進度
    """
    from datetime import datetime
    import threading
    
    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)
    
    if not tenant:
        return jsonify({"success": False, "error": "找不到此租戶"}), 404
    
    folder_url = request.json.get("folder_url") or tenant.google_drive_folder_url
    
    if not folder_url:
        return jsonify({"success": False, "error": "請先設定 Google Drive 資料夾網址"}), 400
    
    # Check if there's already an active sync
    from src.namecard.infrastructure.storage.tenant_db import get_tenant_db
    db = get_tenant_db()
    active_sync = db.get_active_drive_sync(tenant_id)
    
    if active_sync:
        return jsonify({
            "success": False,
            "error": "此租戶已有進行中的同步任務",
            "active_sync_id": active_sync.get("id"),
        }), 400
    
    try:
        from src.namecard.infrastructure.storage.google_drive_client import (
            GoogleDriveClient,
            get_google_drive_client,
        )
        from src.namecard.core.services.drive_sync_service import DriveSyncService
        
        drive_client = get_google_drive_client()
        
        if not drive_client:
            return jsonify({
                "success": False,
                "error": "Google Drive 服務未設定",
            }), 400
        
        # Parse folder ID for logging
        folder_id = GoogleDriveClient.extract_folder_id(folder_url)
        
        # Create sync log
        sync_log = db.create_drive_sync_log(
            tenant_id=tenant_id,
            folder_url=folder_url,
            folder_id=folder_id,
        )
        
        # Update tenant status
        db.update_tenant(tenant_id, {
            "google_drive_folder_url": folder_url,
            "google_drive_sync_status": "processing",
        })
        
        # Get tenant's API keys
        from simple_config import settings
        
        google_api_key = tenant.google_api_key if not tenant.use_shared_google_api else settings.google_api_key
        notion_api_key = tenant.notion_api_key if not tenant.use_shared_notion_api else settings.notion_api_key
        notion_database_id = tenant.notion_database_id
        
        # Start sync in background thread
        def run_sync():
            try:
                sync_service = DriveSyncService(
                    tenant_id=tenant_id,
                    drive_client=drive_client,
                    google_api_key=google_api_key,
                    notion_api_key=notion_api_key,
                    notion_database_id=notion_database_id,
                )
                
                def progress_callback(progress):
                    # Update database with progress
                    db.update_drive_sync_log(
                        log_id=sync_log["id"],
                        total_files=progress.total_files,
                        processed_files=progress.processed_files,
                        success_count=progress.success_count,
                        error_count=progress.error_count,
                        skipped_count=progress.skipped_count,
                        status=progress.status,
                        error_log="\n".join(progress.errors) if progress.errors else None,
                    )
                
                result = sync_service.sync_folder(
                    folder_url=folder_url,
                    progress_callback=progress_callback,
                    user_id=f"drive_sync_{tenant_id}",
                )
                
                # Update final status
                db.update_drive_sync_log(
                    log_id=sync_log["id"],
                    total_files=result.total_files,
                    processed_files=result.processed_files,
                    success_count=result.success_count,
                    error_count=result.error_count,
                    skipped_count=result.skipped_count,
                    status=result.status,
                    error_log="\n".join(result.errors) if result.errors else None,
                    completed=True,
                )
                
                # Update tenant status
                db.update_tenant(tenant_id, {
                    "google_drive_sync_status": result.status,
                    "google_drive_last_sync": datetime.now().isoformat(),
                })
                
                logger.info(
                    "DRIVE_SYNC_COMPLETED",
                    tenant_id=tenant_id,
                    status=result.status,
                    success=result.success_count,
                    errors=result.error_count,
                )
                
            except Exception as e:
                logger.error("DRIVE_SYNC_THREAD_ERROR", tenant_id=tenant_id, error=str(e))
                db.update_drive_sync_log(
                    log_id=sync_log["id"],
                    status="failed",
                    error_log=str(e),
                    completed=True,
                )
                db.update_tenant(tenant_id, {
                    "google_drive_sync_status": "failed",
                })
        
        # Start background thread
        sync_thread = threading.Thread(target=run_sync, daemon=True)
        sync_thread.start()
        
        logger.info(
            "DRIVE_SYNC_STARTED",
            tenant_id=tenant_id,
            sync_log_id=sync_log["id"],
            folder_id=folder_id,
        )
        
        return jsonify({
            "success": True,
            "message": "同步已開始",
            "sync_id": sync_log["id"],
        })
        
    except Exception as e:
        logger.error("DRIVE_SYNC_START_ERROR", tenant_id=tenant_id, error=str(e))
        return jsonify({"success": False, "error": f"啟動同步失敗: {str(e)}"}), 500


@admin_bp.route("/api/drive/sync-status/<tenant_id>")
@login_required
def get_drive_sync_status(tenant_id: str):
    """
    取得 Google Drive 同步狀態
    
    前端可輪詢此端點以取得即時進度
    """
    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)
    
    if not tenant:
        return jsonify({"success": False, "error": "找不到此租戶"}), 404
    
    from src.namecard.infrastructure.storage.tenant_db import get_tenant_db
    db = get_tenant_db()
    
    # Get active sync or last sync
    active_sync = db.get_active_drive_sync(tenant_id)
    
    if active_sync:
        return jsonify({
            "success": True,
            "status": active_sync.get("status"),
            "is_syncing": True,
            "sync_id": active_sync.get("id"),
            "total_files": active_sync.get("total_files", 0),
            "processed_files": active_sync.get("processed_files", 0),
            "success_count": active_sync.get("success_count", 0),
            "error_count": active_sync.get("error_count", 0),
            "skipped_count": active_sync.get("skipped_count", 0),
            "progress_percent": round(
                (active_sync.get("processed_files", 0) / max(active_sync.get("total_files", 1), 1)) * 100, 1
            ),
            "started_at": active_sync.get("started_at"),
        })
    
    # Get last sync log
    sync_logs = db.get_tenant_drive_sync_logs(tenant_id, limit=1)
    last_sync = sync_logs[0] if sync_logs else None
    
    return jsonify({
        "success": True,
        "status": tenant.google_drive_sync_status or "idle",
        "is_syncing": False,
        "last_sync": {
            "sync_id": last_sync.get("id") if last_sync else None,
            "status": last_sync.get("status") if last_sync else None,
            "total_files": last_sync.get("total_files") if last_sync else 0,
            "success_count": last_sync.get("success_count") if last_sync else 0,
            "error_count": last_sync.get("error_count") if last_sync else 0,
            "completed_at": last_sync.get("completed_at") if last_sync else None,
        } if last_sync else None,
        "folder_url": tenant.google_drive_folder_url,
        "last_sync_time": tenant.google_drive_last_sync,
    })


@admin_bp.route("/api/drive/sync-logs/<tenant_id>")
@login_required
def get_drive_sync_logs(tenant_id: str):
    """
    取得租戶的同步歷史記錄
    """
    tenant_service = get_tenant_service()
    tenant = tenant_service.get_tenant_by_id(tenant_id)
    
    if not tenant:
        return jsonify({"success": False, "error": "找不到此租戶"}), 404
    
    limit = request.args.get("limit", 10, type=int)
    
    from src.namecard.infrastructure.storage.tenant_db import get_tenant_db
    db = get_tenant_db()
    
    logs = db.get_tenant_drive_sync_logs(tenant_id, limit=limit)
    
    return jsonify({
        "success": True,
        "logs": logs,
    })


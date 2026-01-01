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
    static_folder=os.path.join(_project_root, "static/admin")
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
        "total_processed": 0, "total_saved": 0, "total_errors": 0, "active_tenants": 0
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
        admin_username=session.get("admin_username")
    )


# ==================== Tenant Management ====================

@admin_bp.route("/tenants")
@login_required
def list_tenants():
    """List all tenants"""
    tenant_service = get_tenant_service()
    tenants = tenant_service.list_tenants(include_inactive=True)

    return render_template(
        "tenants/list.html",
        tenants=tenants,
        admin_username=session.get("admin_username")
    )


@admin_bp.route("/tenants/new", methods=["GET", "POST"])
@login_required
def create_tenant():
    """Create new tenant"""
    if request.method == "POST":
        try:
            # Get form data
            tenant_request = TenantCreateRequest(
                name=request.form.get("name", "").strip(),
                slug=request.form.get("slug", "").strip() or None,
                line_channel_id=request.form.get("line_channel_id", "").strip(),
                line_channel_access_token=request.form.get("line_channel_access_token", "").strip(),
                line_channel_secret=request.form.get("line_channel_secret", "").strip(),
                notion_api_key=request.form.get("notion_api_key", "").strip(),
                notion_database_id=request.form.get("notion_database_id", "").strip(),
                google_api_key=request.form.get("google_api_key", "").strip() or None,
                use_shared_google_api=request.form.get("use_shared_google_api") == "on",
                daily_card_limit=int(request.form.get("daily_card_limit", 50)),
                batch_size_limit=int(request.form.get("batch_size_limit", 10)),
            )

            tenant_service = get_tenant_service()
            tenant = tenant_service.create_tenant(tenant_request)

            flash(f"租戶 '{tenant.name}' 建立成功", "success")
            return redirect(url_for("admin.list_tenants"))

        except Exception as e:
            logger.error("Failed to create tenant", error=str(e))
            flash(f"建立失敗: {str(e)}", "error")

    return render_template(
        "tenants/form.html",
        tenant=None,
        is_edit=False,
        admin_username=session.get("admin_username")
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

            # LINE Channel ID - always check for updates
            line_channel_id = request.form.get("line_channel_id", "").strip()
            if line_channel_id and line_channel_id != tenant.line_channel_id:
                update_data["line_channel_id"] = line_channel_id

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
                tenant_service.update_tenant(tenant_id, update_request)
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
        admin_username=session.get("admin_username")
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
        "total_processed": 0, "total_saved": 0, "total_errors": 0,
        "total_api_calls": 0, "active_days": 0, "avg_daily_processed": 0,
        "success_rate": 0, "error_rate": 0
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
        admin_username=session.get("admin_username")
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
        "google": {"status": "unknown"}
    }

    # Test LINE Bot API
    try:
        from linebot import LineBotApi
        line_api = LineBotApi(tenant.line_channel_access_token)
        # Get bot info to verify token
        bot_info = line_api.get_bot_info()
        results["line"] = {
            "status": "success",
            "bot_name": bot_info.display_name if hasattr(bot_info, 'display_name') else "OK"
        }
    except Exception as e:
        results["line"] = {"status": "error", "message": str(e)}

    # Test Notion API
    try:
        from notion_client import Client
        notion = Client(auth=tenant.notion_api_key)
        db_info = notion.databases.retrieve(database_id=tenant.notion_database_id)
        results["notion"] = {
            "status": "success",
            "database_title": db_info.get("title", [{}])[0].get("plain_text", "OK") if db_info.get("title") else "OK"
        }
    except Exception as e:
        results["notion"] = {"status": "error", "message": str(e)}

    # Test Google API (if tenant has custom key)
    if tenant.google_api_key and not tenant.use_shared_google_api:
        try:
            import google.generativeai as genai
            genai.configure(api_key=tenant.google_api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            # Simple test
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

    return jsonify({
        "users": users,
        "total_users": user_count
    })

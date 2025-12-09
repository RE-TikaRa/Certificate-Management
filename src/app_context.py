from dataclasses import dataclass

from .data.database import Database
from .logger import configure_logging
from .services.attachment_manager import AttachmentManager
from .services.award_service import AwardService
from .services.backup_manager import BackupManager
from .services.import_export import ImportExportService
from .services.major_service import MajorService
from .services.member_service import MemberService
from .services.school_service import SchoolService
from .services.settings_service import SettingsService
from .services.statistics_service import StatisticsService


@dataclass
class AppContext:
    db: Database
    settings: SettingsService
    attachments: AttachmentManager
    backup: BackupManager
    importer: ImportExportService
    statistics: StatisticsService
    awards: AwardService
    majors: MajorService
    schools: SchoolService
    members: MemberService


def bootstrap(debug: bool = False) -> AppContext:
    configure_logging(debug_enabled=debug)

    db = Database()
    db.initialize()

    settings = SettingsService(db)
    attachments = AttachmentManager(db, settings)
    awards = AwardService(db, attachments)
    backup = BackupManager(db, settings)
    importer = ImportExportService(db, attachments)
    statistics = StatisticsService(db)
    majors = MajorService(db)
    schools = SchoolService(db)
    members = MemberService(db)

    backup.schedule_jobs()

    return AppContext(
        db=db,
        settings=settings,
        attachments=attachments,
        backup=backup,
        importer=importer,
        statistics=statistics,
        awards=awards,
        majors=majors,
        schools=schools,
        members=members,
    )

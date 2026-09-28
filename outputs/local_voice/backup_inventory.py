"""Read-only backup inventory; suffixes describe files, not encryption validity."""
import stat
from pathlib import Path


def inventory(directory):
    report={'encrypted_archive_files':0,'legacy_zip_files':0,'incomplete_files':0,
            'total_bytes':0,'oldest_archive_mtime':None,'newest_archive_mtime':None,
            'skipped_links':0,'read_errors':0}
    directory=Path(directory)
    try:root_info=directory.lstat()
    except FileNotFoundError:return report
    except OSError:
        report['read_errors']=1;return report
    if stat.S_ISLNK(root_info.st_mode) or getattr(root_info,'st_file_attributes',0)&0x400:
        report['skipped_links']=1
        return report
    try:entries=list(directory.iterdir())
    except OSError:
        report['read_errors']=1
        return report
    for path in entries:
        try:
            info=path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                report['skipped_links']+=1;continue
            if not stat.S_ISREG(info.st_mode):continue
            suffix=path.suffix.lower()
            if suffix not in ('.dtbackup','.dtledger','.zip','.verifying','.uploading','.tmp'):continue
            report['total_bytes']+=info.st_size
            if suffix=='.dtbackup':
                report['encrypted_archive_files']+=1
                for key,select in (('oldest_archive_mtime',min),('newest_archive_mtime',max)):
                    report[key]=info.st_mtime if report[key] is None else select(report[key],info.st_mtime)
            elif suffix=='.zip':report['legacy_zip_files']+=1
            elif suffix in ('.verifying','.uploading','.tmp'):report['incomplete_files']+=1
        except OSError:report['read_errors']+=1
    return report

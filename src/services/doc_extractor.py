"""
学生信息提取工具
从.doc文档中提取关键学生信息用于成员录入
"""

import re
import subprocess
import os
from pathlib import Path


class DocInfoExtractor:
    """文档信息提取器 - 用于从.doc文件提取成员信息"""
    
    def __init__(self, doc_path):
        self.doc_path = doc_path
        self.text_content = ""
        self.member_info = {}
    
    def extract_text_from_doc(self):
        """使用PowerShell和Word COM对象提取.doc文件文本"""
        # 转换路径为绝对路径并规范化
        abs_path = os.path.abspath(self.doc_path).replace('/', '\\')
        
        # 使用 -EncodedCommand 避免路径中的特殊字符问题
        ps_script = f'''
        try {{
            $word = New-Object -ComObject Word.Application
            $word.Visible = $false
            $word.DisplayAlerts = 0
            $doc = $word.Documents.Open('{abs_path}', $false, $true)
            $text = $doc.Content.Text
            $doc.Close($false)
            $word.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($doc) | Out-Null
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
            [GC]::Collect()
            [GC]::WaitForPendingFinalizers()
            Write-Output $text
        }} catch {{
            Write-Error $_.Exception.Message
            exit 1
        }}
        '''
        
        try:
            # Windows PowerShell 使用系统默认编码（通常是 GBK）
            # 使用 errors='replace' 处理编码问题
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                capture_output=True,
                text=True,
                encoding='gbk',  # Windows 中文环境使用 GBK
                errors='replace',  # 替换无法解码的字符
                timeout=30  # 30秒超时
            )
            
            if result.returncode == 0 and result.stdout.strip():
                self.text_content = result.stdout.strip()
                return True
            else:
                # 记录详细错误信息
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                import logging
                logging.getLogger(__name__).error(f"PowerShell 错误: {error_msg}")
                return False
        except subprocess.TimeoutExpired:
            raise Exception("文档处理超时（30秒），文件可能过大或损坏")
        except Exception as e:
            raise Exception(f"提取文本时出错: {e}")
    
    def extract_gender(self):
        """提取性别"""
        match = re.search(r'性别[^\u4e00-\u9fa5]*(男|女)', self.text_content)
        if match:
            self.member_info['gender'] = match.group(1)
        else:
            self.member_info['gender'] = None
    
    def extract_id_card(self):
        """提取身份证号"""
        patterns = [
            r'证件号码[^\d]*(\d{17}[\dXx])',
            r'身份证[号]?[^\d]*(\d{17}[\dXx])',
            r'(?:^|[^\d])(\d{17}[\dXx])(?:[^\d]|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                id_card = match.group(1)
                if len(id_card) == 18:
                    self.member_info['id_card'] = id_card
                    return
        
        self.member_info['id_card'] = None
    
    def extract_phone(self):
        """提取手机号"""
        patterns = [
            r'手机号码[^\d]*(1[3-9]\d{9})',
            r'联系电话[^\d]*(1[3-9]\d{9})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                self.member_info['phone'] = match.group(1)
                return
        
        self.member_info['phone'] = None
    
    def extract_student_id(self):
        """提取学号"""
        patterns = [
            r'学号[^\d]*(\d{10,})',  # 学号后跟10位以上数字
            r'学号\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                self.member_info['student_id'] = match.group(1)
                return
        
        self.member_info['student_id'] = None
    
    def extract_email(self):
        """提取邮箱"""
        patterns = [
            r'邮箱[^\w@]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'电子邮件[^\w@]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                self.member_info['email'] = match.group(1)
                return
        
        self.member_info['email'] = None
    
    def extract_major(self):
        """提取专业"""
        patterns = [
            # 优先匹配"及其xxx"结构的完整专业名
            r'专业[^\u4e00-\u9fa5]*([^\s\n]+及其[^\s\n]+)',
            # 匹配"与xxx"结构的完整专业名（如"水土保持与荒漠化防治"）
            r'专业[^\u4e00-\u9fa5]*([^\s\n]+与[^\s\n]+)',
            # 匹配以常见专业后缀结尾的完整名称
            r'专业[^\u4e00-\u9fa5]*([^\s\n]+(?:工程|技术|管理|科学|设计|艺术|防治|保护|栽培|鉴定))',
            # 匹配以"学"结尾的专业（包括2字专业如"农学"、"林学"）
            r'专业[^\u4e00-\u9fa5]*([^\s\n]+学)',
            # 匹配2-25个中文字符（支持长专业名）
            r'专业[^\u4e00-\u9fa5]*([一-龥]{2,25})',
            # 匹配中英文混合（如"英语"）
            r'专业[^\u4e00-\u9fa5]*([一-龥a-zA-Z]{2,25})',
            # 最后尝试：专业后的非空白内容
            r'专业\s*([^\s\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                major = match.group(1).strip()
                # 清理可能的标点符号（但保留"与"、"及"等关键字）
                major = re.sub(r'[：:、，,。.；;！!？?（）()]', '', major)
                # 支持2个字及以上的专业名称
                if len(major) >= 2 and '专业' not in major:
                    self.member_info['major'] = major
                    return
        
        self.member_info['major'] = None
    
    def extract_class(self):
        """提取班级"""
        patterns = [
            r'班级[^\d]*(\d+[^\s\n]+\d*)',
            r'班级\s*([^\s\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                class_name = match.group(1).strip()
                if len(class_name) > 0:
                    self.member_info['class_name'] = class_name
                    return
        
        self.member_info['class_name'] = None
    
    def extract_college(self):
        """提取学院"""
        patterns = [
            r'院系[^\u4e00-\u9fa5]*([^\s\n]+学院)',
            r'学院[^\u4e00-\u9fa5]*([^\s\n]+学院)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text_content)
            if match:
                college = match.group(1)
                if '学院' in college:
                    self.member_info['college'] = college
                    return
        
        # 备选方案
        match = re.search(r'院系\s*([^\s\n]+)', self.text_content)
        if match:
            self.member_info['college'] = match.group(1)
        else:
            self.member_info['college'] = None
    
    def extract_all(self):
        """
        提取所有信息
        
        Returns:
            dict: 包含成员信息的字典，键名对应 TeamMember 模型字段
                  {
                      'gender': str,
                      'id_card': str,
                      'phone': str,
                      'student_id': str,
                      'email': str,
                      'major': str,
                      'class_name': str,
                      'college': str
                  }
        Raises:
            Exception: 文档读取失败时抛出异常
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 提取文本
        try:
            if not self.extract_text_from_doc():
                raise Exception(
                    "无法提取文档文本。\n"
                    "可能的原因：\n"
                    "1. 未安装 Microsoft Word\n"
                    "2. Word 进程被占用\n"
                    "3. 文件损坏或格式不正确\n"
                    "建议：尝试在 Word 中打开文件确认是否正常"
                )
        except subprocess.TimeoutExpired:
            raise Exception("文档处理超时，文件可能过大")
        except Exception as e:
            logger.error(f"提取文档失败: {e}", exc_info=True)
            raise
        
        # 检查文本是否有效
        if not self.text_content:
            raise Exception("提取的文本为空")
        
        # 提取各项信息（8个字段，不包括姓名）
        self.extract_gender()
        self.extract_id_card()
        self.extract_phone()
        self.extract_student_id()
        self.extract_email()
        self.extract_major()
        self.extract_class()
        self.extract_college()
        
        return self.member_info
    
    def get_field_count(self):
        """获取成功提取的字段数量"""
        return sum(1 for v in self.member_info.values() if v is not None)


def extract_member_info_from_doc(doc_path, email_suffix=None):
    """
    便捷函数：从.doc文件提取成员信息
    
    Args:
        doc_path: .doc文件的绝对路径
        email_suffix: 邮箱后缀，如果邮箱为空且有学号，则自动生成邮箱
    
    Returns:
        dict: 成员信息字典，未提取到的字段值为 None
    
    Raises:
        FileNotFoundError: 文件不存在
        Exception: 提取失败
    """
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"文件不存在: {doc_path}")
    
    extractor = DocInfoExtractor(doc_path)
    member_info = extractor.extract_all()
    
    # 如果邮箱为空且有学号，自动生成邮箱
    if not member_info.get('email') and member_info.get('student_id') and email_suffix:
        member_info['email'] = f"{member_info['student_id']}{email_suffix}"
    
    return member_info


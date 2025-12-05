"""
Form validators for data integrity and consistency.
"""

from __future__ import annotations

import re
from typing import Any


class FormValidator:
    """Centralized form field validators."""

    @staticmethod
    def validate_id_card(card: str) -> tuple[bool, str]:
        """
        Validate 18-digit Chinese ID card number.

        Args:
            card: ID card string

        Returns:
            (is_valid, error_message)
        """
        if not card:
            return True, ""  # Allow empty

        card = card.strip()
        if len(card) != 18:
            return False, "身份证号必须为18位数字"

        if not card.isdigit():
            return False, "身份证号只能包含数字"

        # 可选：验证校验位（增强版本）
        # return FormValidator._validate_id_card_checksum(card)
        return True, ""

    @staticmethod
    def validate_email(email: str) -> tuple[bool, str]:
        """
        Validate email format.

        Args:
            email: Email string

        Returns:
            (is_valid, error_message)
        """
        if not email:
            return True, ""  # Allow empty

        email = email.strip()
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(pattern, email):
            return False, "邮箱格式不正确"

        if len(email) > 128:
            return False, "邮箱长度不能超过128字符"

        return True, ""

    @staticmethod
    def validate_phone(phone: str) -> tuple[bool, str]:
        """
        Validate Chinese mobile phone number (11 digits starting with 1).

        Args:
            phone: Phone number string

        Returns:
            (is_valid, error_message)
        """
        if not phone:
            return True, ""  # Allow empty

        phone = phone.strip()

        # Chinese mobile numbers: 11 digits, starting with 1
        pattern = r"^1[3-9]\d{9}$"

        if not re.match(pattern, phone):
            return False, "手机号格式不正确，应为11位数字"

        return True, ""

    @staticmethod
    def validate_age(age_input: str | int) -> tuple[bool, str]:
        """
        Validate age range (1-120).

        Args:
            age_input: Age as string or int

        Returns:
            (is_valid, error_message)
        """
        if not age_input:
            return True, ""  # Allow empty

        try:
            age = int(age_input) if isinstance(age_input, str) else age_input

            if age < 1 or age > 120:
                return False, "年龄必须在1-120之间"

            return True, ""
        except (ValueError, TypeError):
            return False, "年龄必须是数字"

    @staticmethod
    def validate_student_id(student_id: str) -> tuple[bool, str]:
        """
        Validate student ID length (typically 6-20 characters).

        Args:
            student_id: Student ID string

        Returns:
            (is_valid, error_message)
        """
        if not student_id:
            return True, ""  # Allow empty

        student_id = student_id.strip()

        if len(student_id) < 6 or len(student_id) > 20:
            return False, "学号长度应在6-20位之间"

        if not student_id.isalnum():
            return False, "学号只能包含字母和数字"

        return True, ""

    @staticmethod
    def validate_competition_name(name: str) -> tuple[bool, str]:
        """
        Validate competition/award name.

        Args:
            name: Competition name

        Returns:
            (is_valid, error_message)
        """
        if not name:
            return False, "比赛名称不能为空"

        name = name.strip()

        if len(name) > 255:
            return False, "比赛名称不能超过255字符"

        if len(name) < 2:
            return False, "比赛名称至少需要2个字符"

        return True, ""

    @staticmethod
    def validate_certificate_code(code: str) -> tuple[bool, str]:
        """
        Validate certificate code format.

        Args:
            code: Certificate code string

        Returns:
            (is_valid, error_message)
        """
        if not code:
            return True, ""  # Allow empty

        code = code.strip()

        if len(code) > 128:
            return False, "证书编号长度不能超过128字符"

        return True, ""

    @staticmethod
    def validate_remarks(remarks: str) -> tuple[bool, str]:
        """
        Validate remarks field.

        Args:
            remarks: Remarks text

        Returns:
            (is_valid, error_message)
        """
        if not remarks:
            return True, ""  # Allow empty

        remarks = remarks.strip()

        if len(remarks) > 1000:
            return False, "备注长度不能超过1000字符"

        return True, ""

    @staticmethod
    def validate_member_info(member_data: dict[str, Any]) -> list[str]:
        """
        Validate complete member information.

        Args:
            member_data: Dictionary containing member fields

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        # Name is required
        name = member_data.get("name", "").strip()
        if not name:
            errors.append("成员姓名不能为空")
        elif len(name) > 128:
            errors.append("成员姓名不能超过128字符")

        # Validate optional fields
        if id_card := member_data.get("id_card"):
            valid, msg = FormValidator.validate_id_card(id_card)
            if not valid:
                errors.append(f"身份证号: {msg}")

        if phone := member_data.get("phone"):
            valid, msg = FormValidator.validate_phone(phone)
            if not valid:
                errors.append(f"手机号: {msg}")

        if email := member_data.get("email"):
            valid, msg = FormValidator.validate_email(email)
            if not valid:
                errors.append(f"邮箱: {msg}")

        if student_id := member_data.get("student_id"):
            valid, msg = FormValidator.validate_student_id(student_id)
            if not valid:
                errors.append(f"学号: {msg}")

        return errors

    @staticmethod
    def validate_award_form(form_data: dict[str, Any]) -> list[str]:
        """
        Validate complete award/honor form.

        Args:
            form_data: Dictionary containing award fields

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        # Competition name is required
        valid, msg = FormValidator.validate_competition_name(form_data.get("competition_name", ""))
        if not valid:
            errors.append(msg)

        # Certificate code validation
        if code := form_data.get("certificate_code"):
            valid, msg = FormValidator.validate_certificate_code(code)
            if not valid:
                errors.append(msg)

        # Remarks validation
        if remarks := form_data.get("remarks"):
            valid, msg = FormValidator.validate_remarks(remarks)
            if not valid:
                errors.append(msg)

        # At least one member required
        members = form_data.get("members", [])
        if not members:
            errors.append("请至少添加一名成员")
        else:
            # Validate each member
            for i, member in enumerate(members, 1):
                member_errors = FormValidator.validate_member_info(member)
                for error in member_errors:
                    errors.append(f"成员{i}: {error}")

        return errors

    @staticmethod
    def _validate_id_card_checksum(card: str) -> tuple[bool, str]:
        """
        Validate Chinese ID card checksum (advanced).
        Reference: https://zh.wikipedia.org/wiki/%E4%B8%AD%E5%8D%8E%E4%BA%BA%E6%B0%91%E5%85%B1%E5%92%8C%E5%9B%BD%E8%BA%AB%E4%BB%BD%E8%AF%81
        """
        if len(card) != 18:
            return False, "身份证号必须为18位"

        weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        check_codes = "10X98765432"

        try:
            checksum = sum(int(card[i]) * weights[i] for i in range(17)) % 11
            return card[17] == check_codes[checksum], "身份证号校验位错误"
        except (ValueError, IndexError):
            return False, "身份证号格式不正确"

    @staticmethod
    def calculate_age_from_id_card(id_card: str) -> int | None:
        """
        从身份证号计算年龄。

        支持18位和15位身份证号：
        - 18位：YYYYMMDDXXXXXXXXXXXXXX（前8位为出生日期）
        - 15位：YYMMDDXXXXXXXXXXXXXX（前6位为出生日期，YY表示年份）

        Args:
            id_card: 身份证号

        Returns:
            年龄（整数）或 None 如果无法计算
        """
        from datetime import datetime

        if not id_card:
            return None

        id_card = id_card.strip()

        try:
            if len(id_card) == 18:
                # 18位身份证
                birth_year = int(id_card[0:4])
                birth_month = int(id_card[4:6])
                birth_day = int(id_card[6:8])
            elif len(id_card) == 15:
                # 15位身份证（旧版）
                yy = int(id_card[0:2])
                # 如果YY > 当前年份的后两位，说明是19xx年；否则是20xx年
                current_year = datetime.today().year
                current_yy = current_year % 100

                if yy > current_yy:
                    birth_year = 1900 + yy
                else:
                    birth_year = 2000 + yy

                birth_month = int(id_card[2:4])
                birth_day = int(id_card[4:6])
            else:
                return None

            # 验证日期有效性
            birth_date = datetime(birth_year, birth_month, birth_day)
            today = datetime.today()

            # 计算年龄
            age = today.year - birth_date.year
            # 如果今年生日还没有，年龄减1
            if (today.month, today.day) < (birth_date.month, birth_date.day):
                age -= 1

            return age if 0 <= age <= 120 else None
        except (ValueError, IndexError):
            return None

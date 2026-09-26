"""Narrow comparison baseline for explicit Chinese verbal repairs.

This never rewrites saved ASR text. Unsupported/quoted repairs remain literal.
Only a matching replacement unit with an explicit correction cue is accepted.
"""
import re

NUMBER = r'[0-9零〇一二兩三四五六七八九十百千萬]+'
CUE = r'[，,]\s*(?:(?:啊\s*)?不對|啊\s*不是)[，,]?\s*(?:(?:是|改成)\s*)?'
START = r'(?<![0-9零〇一二兩三四五六七八九十百千萬億負正+−\-.,．點点])'
ADJACENT = re.compile(
    START +
    rf'(?P<old>{NUMBER})(?P<unit>點|時|分|杯|份|個|張|盒|瓶|件|元)'
    rf'(?P<half>半)?{CUE}(?P<new>{NUMBER})(?P=unit)(?P<new_half>半)?'
    rf'(?![0-9零〇一二兩三四五六七八九十百千萬億半])')
REPEATED_PLACE = re.compile(
    START + rf'{NUMBER}(?P<unit>點|時)(?:半)?'
    rf'(?P<context>(?:到|去)[\u4e00-\u9fff]{{1,12}})'
    rf'{CUE}(?P<new>{NUMBER})(?P=unit)(?P<new_half>半)?(?P=context)(?![\u4e00-\u9fff0-9])')
ORDER = re.compile(
    rf'(?P<prefix>想要|我要|要買|幫我買|請給我)(?P<old>{NUMBER})'
    rf'(?P<unit>杯|份|個|張|盒|瓶|件)'
    rf'(?P<item>[^，,。；;！？!?\n0-9零〇一二兩三四五六七八九十百千萬]{{1,16}})'
    rf'{CUE}(?P<new>{NUMBER})(?P=unit)就好')
QUOTED = re.compile(r'[「」『』“”"‘’]|(?:他說|她說|客戶說|寫著|原話|引述|例如|舉例)')


def comparison_source(text, replacements=None):
    replacements = replacements if replacements is not None else []
    if QUOTED.search(text):
        return text
    def adjacent(match):
        replacement = match['new'] + match['unit'] + (match['new_half'] or '')
        replacements.append(replacement)
        return replacement
    def repeated_place(match):
        if re.search('不|沒|如果|但是|然後|再|或|還|才|只', match['context']):
            return match.group(0)
        return adjacent(match) + match['context']
    repaired = REPEATED_PLACE.sub(repeated_place, text)
    repaired = ADJACENT.sub(adjacent, repaired)

    def order(match):
        # Do not move a quantity across another action, condition or negation.
        if re.search('不|沒|如果|但是|然後|再|或|還|才|只', match['item']):
            return match.group(0)
        replacement = match['new'] + match['unit']
        replacements.append(replacement)
        return match['prefix'] + replacement + match['item']

    repaired = ORDER.sub(order, repaired)
    if repaired == text:
        return text
    # Leading hesitation and adjacent first-person stutter are optional only
    # within this recognized repair path; never remove a request cue.
    repaired = re.sub(r'^(?:(?:嗯|呃|那個)[，,\s]*)+', '', repaired)
    repaired = re.sub(r'我{2,}', '我', repaired)
    return repaired


def validate_repair_values(repaired, edited, replacements):
    # A repair must keep its explicit replacement, even when changing a single
    # Chinese digit would otherwise fit the general edit-distance allowance.
    for value in set(replacements):
        pattern = re.compile(r'(?<![0-9零〇一二兩三四五六七八九十百千萬])'
                             + re.escape(value) + r'(?![0-9零〇一二兩三四五六七八九十百千萬半])')
        if len(pattern.findall(repaired)) != len(pattern.findall(edited)):
            raise ValueError('Formatting changed an explicit correction value')

from dateutil.relativedelta import relativedelta
from ply import lex
from ply import yacc

tokens = ('HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR', 'NUMBER', 'COMMA', 'AND')

t_HOUR = r'hours?'
t_DAY = r'days?'
t_WEEK = r'weeks?'
t_MONTH = r'months?'
t_YEAR = r'years?'
t_COMMA = r','
t_AND = r'and'

t_ignore = r' '


def t_error(t):
    print 'Illegal character "%s"' % t.value[0]
    t.lexer.skip(1)


def t_NUMBER(t):
    r'\d+'
    try:
        t.value = int(t.value)
    except ValueError:
        t.value = 0
    return t


lexer = lex.lex()


def p_expression_comma(p):
    """
    expression : expression COMMA expression
    """
    p[0] = p[1] + p[3]


def p_expression_year(p):
    'expression : NUMBER YEAR'
    p[0] = relativedelta(years=p[1])


def p_expression_month(p):
    'expression : NUMBER MONTH'
    p[0] = relativedelta(months=p[1])


def p_expression_week(p):
    'expression : NUMBER WEEK'
    p[0] = relativedelta(days=7*p[1])


def p_expression_day(p):
    'expression : NUMBER DAY'
    p[0] = relativedelta(days=p[1])


def p_expression_HOUR(p):
    'expression : NUMBER HOUR'
    p[0] = relativedelta(hours=p[1])


parser = yacc.yacc()
if __name__ == '__main__':
    while True:
        try:
            s = raw_input('time_delta> ')
        except EOFError:
            break
        if not s:
            continue
        result = parser.parse(s)
        print result

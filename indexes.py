from django.contrib.postgres.indexes import GistIndex
from django.db.models import Index


class UpperGistIndex(GistIndex):
    """
        В операции __icontains... Используется оператор UPPER.
        Cделан override дефолтного GistIndex с указанием поля UPPER()

        Возможно нужно будет удалять этот индекс, когда введут поддержку из коробки.
    """

    def create_sql(self, model, schema_editor, using='', **kwargs):
        statement = super(UpperGistIndex, self).create_sql(
            model, schema_editor, using, **kwargs
        )
        quote_name = statement.parts['columns'].quote_name

        def upper_quoted(column):
            return 'UPPER({0})'.format(quote_name(column))

        statement.parts['columns'].quote_name = upper_quoted
        return statement


class UpperGistIndexCastedToText(GistIndex):
    """
        Дополнительные **kwargs не получается прокиднуть в Base Index class (похоже на баг джанги)
        Сделан тот же самый GistUpperIndex, но в этом случае мы можем осуществлять поиск по int\bigint полям

        Для чего это сделано:
            Если осуществляется поиск по int\bigint полю в операции __icontains.
                Это поле кастится на уровне БД в text

        Как это выглядит на уровне БД:
            explain analyze select * from education_studygroup where
                UPPER("education_studygroup"."study_group_id"::text) LIKE UPPER('%2451%');
    """

    def create_sql(self, model, schema_editor, using='', **kwargs):
        statement = super(UpperGistIndexCastedToText, self).create_sql(
            model, schema_editor, using, **kwargs
        )
        quote_name = statement.parts['columns'].quote_name

        def upper_quoted(column):
            return 'UPPER({0}::text)'.format(quote_name(column))

        statement.parts['columns'].quote_name = upper_quoted
        return statement


class UpperIndex(Index):
    """
        Тоже самое. что и UpperGistIndex.
        Для операций __iexact
    """

    def create_sql(self, model, schema_editor, using='', **kwargs):
        statement = super(UpperIndex, self).create_sql(
            model, schema_editor, using, **kwargs
        )
        quote_name = statement.parts['columns'].quote_name

        def upper_quoted(column):
            return 'UPPER({0})'.format(quote_name(column))

        statement.parts['columns'].quote_name = upper_quoted
        return statement

# Как можно улучшить производительность Django приложений благодаря построению новых индексов в PostgreSQL

Для начала нужно познакомиться с базой того, как Django ORM конвертирует ваш запрос в SQL:

# __iexact

Python:
```python
qs = qs.all()
_iexact = qs.filter(first_name__iexact='олег')
_iexact_sql = _iexact.query.sql_with_params()
```

SQL:
```sql
SELECT * FROM "users_user" WHERE UPPER("users_user"."first_name"::text) = UPPER('олег');
```

# __icontains

Python:
```python
qs = qs.all()
_icontains = qs.filter(first_name__icontains='олег')
_icontains_sql = _icontains.query.sql_with_params()
```
SQL:
```sql
SELECT * FROM "users_user" WHERE UPPER("users_user"."first_name"::text) LIKE UPPER('%олег%');
```

# __exact

Python:
```python
qs = qs.all()
_exact = qs.filter(first_name__exact='Олег')
_exact_sql = _exact.query.sql_with_params()
```

SQL:
```sql
SELECT * FROM "users_user" WHERE "users_user"."first_name" = 'Олег';
```

# __contains

```python
qs = qs.all()
_contains = qs.filter(first_name__contains='Олег')
_contains_sql = _contains.query.sql_with_params()
```
SQL:
```sql
SELECT * FROM "users_user" WHERE "users_user"."first_name"::text LIKE '%Олег%';
```

Как можно заметить, не всегда очевидно как Django ORM конвертирует в SQL, который выполняется на БД. Особенно это видно в операциях **__icontains**, **__ixact**.

Ожидается, что будет использован поиск по **ILIKE**, но Django использует совсем неочивидный поиск по **UPPER**.

*В этом вся главная особенность работы и почему запросы выполняются долго* 

e.g.: в этой статье будет использоваться поле first_name (самый очевидный пример)

Все индексы, что вы создаете по такому сценарию:


```python
first_name = models.CharField(max_length=255, db_index=True)
```

Создают на бд 2 индекса:

```sql
users_user_first_name_7e5e114b -- используется только для операций __exact, __in
users_user_first_name_7e5e114b_like -- индекс вообще не используется, хотя по своей сути должен отвечать за __contains 
```

Примерный код самих индексов, который выполняет Django в PostgreSQL
```sql
CREATE INDEX users_user_first_name_7e5e114b
    ON public.users_user USING btree
    (f_name COLLATE pg_catalog."default" ASC NULLS LAST);
```

```sql
CREATE INDEX users_user_first_name_7e5e114b_like
    ON public.users_user USING btree
    (f_name COLLATE pg_catalog."default" varchar_pattern_ops ASC NULLS LAST);
```

Когда мы начинаем осуществлять поиск по **__icontains**, **__iexact**, **__contains** эти индексы попросту бесполезны, они не несут в себе того функционала, которое должно покрывать наши запросы

# Производительность

Сейчас продемонстрирую интересную разницу в плане запроса **С** индесами по этим операциям и **Без**.

Код, который используется, можно увидеть выше

**Данные**: таблица *users_user* - 202427 записей настоящих данных пользователей приложения, не foo bar значения

## Без индексов

### __iexact

```sql
"Gather  (cost=1000.00..8454.37 rows=1012 width=721) (actual time=1.090..104.652 rows=926 loops=1)"
"  Workers Planned: 2"
"  Workers Launched: 2"
"  ->  Parallel Seq Scan on users_user  (cost=0.00..7353.17 rows=422 width=721) (actual time=0.471..72.640 rows=309 loops=3)"
"        Filter: (upper((first_name)::text) = 'ОЛЕГ'::text)"
"        Rows Removed by Filter: 67167"
"Planning time: 2.083 ms"
"Execution time: 117.935 ms"
```

### __icontains
```sql
"Gather  (cost=1000.00..8355.17 rows=20 width=721) (actual time=0.997..114.886 rows=927 loops=1)"
"  Workers Planned: 2"
"  Workers Launched: 2"
"  ->  Parallel Seq Scan on users_user  (cost=0.00..7353.17 rows=8 width=721) (actual time=0.424..90.055 rows=309 loops=3)"
"        Filter: (upper((first_name)::text) ~~ '%ОЛЕГ%'::text)"
"        Rows Removed by Filter: 67167"
"Planning time: 1.993 ms"
"Execution time: 127.784 ms"
```

### __exact
```sql
"Gather  (cost=1000.00..8241.51 rows=992 width=721) (actual time=0.800..65.978 rows=916 loops=1)"
"  Workers Planned: 2"
"  Workers Launched: 2"
"  ->  Parallel Seq Scan on users_user  (cost=0.00..7142.31 rows=413 width=721) (actual time=0.287..38.628 rows=305 loops=3)"
"        Filter: ((first_name)::text = 'Олег'::text)"
"        Rows Removed by Filter: 67170"
"Planning time: 0.191 ms"
"Execution time: 85.363 ms"
```

### __contains

```sql
"Gather  (cost=1000.00..8241.81 rows=995 width=721) (actual time=0.732..73.573 rows=916 loops=1)"
"  Workers Planned: 2"
"  Workers Launched: 2"
"  ->  Parallel Seq Scan on users_user  (cost=0.00..7142.31 rows=415 width=721) (actual time=0.134..42.273 rows=305 loops=3)"
"        Filter: ((first_name)::text ~~ '%Олег%'::text)"
"        Rows Removed by Filter: 67170"
"Planning time: 0.195 ms"
"Execution time: 86.438 ms"
```

## С индексами

### __iexact

```sql
"Index Scan using user_lfm_up_idx on users_user  (cost=0.42..4648.34 rows=1012 width=721) 
(actual time=0.042..32.463 rows=926 loops=1)"
"  Index Cond: (upper((first_name)::text) = 'ОЛЕГ'::text)"
"Planning time: 2.693 ms"
"Execution time: 44.701 ms"
```
### __icontains

```sql
"Index Scan using user_lfm_gist_up_idx on users_user  (cost=0.28..23.73 rows=20 width=721)
 (actual time=0.200..39.449 rows=927 loops=1)"
"  Index Cond: (upper((first_name)::text) ~~ '%ОЛЕГ%'::text)"
"Planning time: 0.119 ms"
"Execution time: 51.209 ms"
```

### __exact

```sql
"Index Scan using user_lfm_idx on users_user  (cost=0.42..4629.41 rows=992 width=721) 
(actual time=0.037..31.041 rows=916 loops=1)"
"  Index Cond: ((first_name)::text = 'Олег'::text)"
"Planning time: 0.349 ms"
"Execution time: 40.134 ms"
```

### __contains

```sql
"Bitmap Heap Scan on users_user  (cost=29.99..1018.67 rows=995 width=721) (actual time=17.723..33.270 rows=916 loops=1)"
"  Recheck Cond: ((first_name)::text ~~ '%Олег%'::text)"
"  Rows Removed by Index Recheck: 11"
"  Heap Blocks: exact=863"
"  ->  Bitmap Index Scan on user_lfm_gist_idx  (cost=0.00..29.74 rows=995 width=0) (actual time=17.614..17.621 rows=927 loops=1)"
"        Index Cond: ((first_name)::text ~~ '%Олег%'::text)"
"Planning time: 0.309 ms"
"Execution time: 44.702 ms"
```

Как можно заметить: разница очень значительная, минимум в 2 раза была улучшена производительность причем на большой выборке данных, с минимальным фильтрами. 

P.S.:
Вы можете посмотреть план запроса напрямую из Django, если не хочется лезть в pgadmin:

```python
qs = qs.all()
_iexact = qs.filter(first_name__iexact='олег')
_iexact_explain = qs.explain(analyze=True)
```

# Автоматизация

Можно было бы занять этим делом DBA, разбираться в производительности, построением индексов вручную под конкретные задачи, 
но программист не был бы программистом (тавтология, но все же), если не хотел улучшить изначально саму архитектуру приложения и все автоматизировать.

Знакомимся: **UpperGistIndex**, **UpperGistIndexCastedToText**, **UpperIndex**, **GistIndex**, **models.Index**

Допустим мы пишем какую-то модель, где у нас будут осуществляться виды поисков: **__iexact**, **__icontains**, **__exact**, **__contains**, **__in**.
В эту модель нужно добавить индексы, которые можно найти в indexes.py. Подключаются они очень просто, посмотрите пример.

Есть также стандартные индексы, которые можно использовать:

Для операций **__exact** и **__in** используется стандартный индекс *models.Index()*

Для операций **__contains** используется стандартный индекс *GistIndex (from django.contrib.postgres.indexes import GistIndex)*

```sql
class User(models.Model):
    first_name = models.CharField(
        max_length=64,
        verbose_name='Имя',

    )
    last_name = models.CharField(
        max_length=64,
        verbose_name='Фамилия',
    )

    middle_name = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Отчество',
    )
    age = models.PositiveSmallIntegerField(
        blank=True,
        verbose_name='Возраст'
    )

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        indexes = [
            UpperGistIndex(fields=['last_name', 'first_name', 'middle_name', ], name='user_lfm_gist_up_idx',
                           opclasses=['gist_trgm_ops', 'gist_trgm_ops', 'gist_trgm_ops', ]),
            GistIndex(fields=['last_name', 'first_name', 'middle_name', ], name='user_lfm_gist_idx',
                      opclasses=['gist_trgm_ops', 'gist_trgm_ops', 'gist_trgm_ops', ]),
            UpperIndex(fields=['last_name', 'first_name', 'middle_name', ], name='user_lfm_up_idx',
                       opclasses=['varchar_pattern_ops', 'varchar_pattern_ops', 'varchar_pattern_ops',]),
            models.Index(fields=['last_name', 'first_name', 'middle_name', ], name='user_lfm_idx'),
            UpperGistIndexCastedToText(fields=['age'], opclasses=['gist_trgm_ops', ], name='user_age_gist_up_idx')
        ]
```

Пояснения по всем **Не** стандартным индексам:

Вы пишите в Django ORM (1) = Нужно добавлять индекс (2):

**__icontains** = *UpperGistIndex* / *UpperGistIndexCastedToText (для числовых полей, "age" в этом примере)* 

**__iexact** = *UpperIndex*

**__exact** / **__in** = *models.Index*

**__contains** = *GistIndex*

Для *GistIndex*, *UpperGistIndex*, *UpperGistIndexCastedToText* требуется **обязательно** указывать opclasses = ['gist_trgm_ops',]

Так же важное уточнение по *opclasses* их должно быть столько, сколько *fields* 

```python
len(fields) == len(opclasses)
```


class Meta.indexes доступны с версии Django 1.11, проблем с подключением этих индексов ни у кого не составит труда.

## PostgreSQL, миграции 

На вашей БД PostgreSQL должно быть установлено расширение **pg_trgm**.

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Так же нужно добавлять в **каждую** миграцию, где у вас было создание GistIndex(UpperGistIndex, UpperGistIndexCastedToText)
Обязательное создание TrigramExtension 1 строкой в миграции.

```python
from django.contrib.postgres.operations import TrigramExtension

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001__initial'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddField()...
    ]
```

# Дополнительно

Для улучшения производительности приложения, убирайте **Meta.ordering** - очень затратная операция подробнее https://docs.djangoproject.com/en/3.1/ref/models/options/#django.db.models.Options.ordering

Делайте сортировки непосредственно в самом QS.

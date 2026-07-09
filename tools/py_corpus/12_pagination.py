def paginate(items, page, per_page):
    start = (page - 1) * per_page
    end = start + per_page
    total_pages = (len(items) + per_page - 1) // per_page
    return {
        "items": items[start:end],
        "page": page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
    }

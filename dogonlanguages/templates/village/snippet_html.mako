<h3>${h.link(request, ctx)}</h3>
% if ctx.languoid and ctx.languoid.in_project:
    ${h.link(request, ctx.languoid)}
% endif
<p>${ctx.description}</p>
"""Request-local atomic spans; internal tokens never enter ordinary word parsing."""
from dataclasses import dataclass
from .source_context_pipeline import prepare, protect_literals, validate_strict
from .leading_english_position import partition
from .quote_preservation import spans
from .punctuation_spacing import restore as restore_punctuation


@dataclass(frozen=True)
class Atom:
    start: int
    end: int
    token: str
    value: str


class Registry:
    def __init__(self,source):
        self.prefix='DTATOM'
        while self.prefix in source:self.prefix+='X'
        self.atoms=[]
        chunks=[]
        cursor=length=0
        for index,(a,b) in enumerate(spans(source)):
            gap=source[cursor:a]
            token=f'{self.prefix}{index}END'
            chunks.extend((gap,token))
            length+=len(gap)
            self.atoms.append(Atom(length,length+len(token),token,source[a:b]))
            length+=len(token)
            cursor=b
        chunks.append(source[cursor:])
        self.masked=''.join(chunks)

    def protect(self,text,*references,literal_terms=()):
        if text!=self.masked:raise ValueError('Atomic source text changed before protection')
        prefix='DTKEEP'
        while any(prefix in value for value in (text,*references)):prefix+='X'
        values={}
        pieces=[]

        def allocate(value):
            name=f'{prefix}{len(values)}END'
            values[name]=value
            return name

        def gap(raw):
            if not raw:return ''
            masked,local_values,_=protect_literals(raw,*references,literal_terms=literal_terms)
            # Consume the producer's explicit dictionary once. No regex or
            # identifier matcher sees any generated quote atom.
            cursor=0
            result=[]
            for name,value in local_values.items():
                if masked.count(name)!=1:raise ValueError('Invalid local literal mapping')
                position=masked.find(name,cursor)
                if position<0:raise ValueError('Local literal order changed')
                result.extend((masked[cursor:position],allocate(value)))
                cursor=position+len(name)
            result.append(masked[cursor:])
            return ''.join(result)

        cursor=0
        for atom in self.atoms:
            if text[atom.start:atom.end]!=atom.token:raise ValueError('Atomic range mismatch')
            pieces.extend((gap(text[cursor:atom.start]),allocate(atom.token)))
            cursor=atom.end
        pieces.append(gap(text[cursor:]))
        return ''.join(pieces),values,prefix

    def restore(self,text):
        if text.count(self.prefix)!=len(self.atoms):raise ValueError('Quote atom missing or duplicated')
        cursor=0
        parts=[]
        for atom in self.atoms:
            if text.count(atom.token)!=1:raise ValueError('Quote atom occurrence changed')
            position=text.find(atom.token,cursor)
            if position<0:raise ValueError('Quote atom order changed')
            parts.extend((text[cursor:position],atom.value))
            cursor=position+len(atom.token)
        parts.append(text[cursor:])
        return ''.join(parts)


async def organize_atomic(source,formatter):
    """formatter(masked_text, request_protector) must retain strict validation."""
    plan=prepare(source)
    positioned=partition(plan.prepared)
    prefix,separator,body=positioned if positioned else ('','',plan.prepared)
    registry=Registry(body)
    rendered=await formatter(registry.masked,registry.protect)
    rendered=registry.restore(rendered)  # After model and Chinese typography.
    rendered,punctuation=restore_punctuation(body,rendered)
    result=prefix+separator+rendered
    validate_strict(plan.prepared,result)
    if [source[a:b] for a,b in spans(source)]!=[result[a:b] for a,b in spans(result)]:
        raise ValueError('Original quotation changed')
    return result,{'prepared':plan.prepared,'policy':plan.policy,
                   'approved_stutter_ranges':list(plan.approved_stutter_ranges),
                   'positioned_prefix':bool(positioned),'atom_count':len(registry.atoms),
                   'punctuation':punctuation}
